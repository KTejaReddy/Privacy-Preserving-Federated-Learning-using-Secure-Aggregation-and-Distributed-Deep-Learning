"""AI Assistant: an enterprise copilot that answers questions about the
platform (rounds, model versions, client contributions, failures, tuning) using
the user's configured AI provider, with a fully functional rule-based fallback
so the feature works even with no external key configured.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.core.security import decrypt_secret
from app.models.models import AIProvider, FederatedRound, InferenceLog, ModelVersion, NodeEvent, TrainingJob, User
from app.schemas.schemas import ChatRequest, ChatResponse
from app.workers.tasks import execute_training_job  # noqa: F401  (imported for auto-registration)

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _platform_context(db: Session) -> dict:
    jobs = db.query(TrainingJob).all()
    rounds = db.query(FederatedRound).order_by(FederatedRound.round_number).all()
    versions = db.query(ModelVersion).all()
    latest_round = rounds[-1] if rounds else None
    running_jobs = [j for j in jobs if j.status == "running"]
    failed_events = db.query(NodeEvent).filter(NodeEvent.severity == "warning").order_by(NodeEvent.id.desc()).limit(10).all()
    return {
        "jobs": len(jobs),
        "running_jobs": len(running_jobs),
        "rounds": len(rounds),
        "latest_round": {
            "number": latest_round.round_number, "accuracy": latest_round.accuracy,
            "loss": latest_round.avg_loss, "participated": latest_round.participated_count,
        } if latest_round else None,
        "versions": [
            {"version": v.version, "job_id": v.job_id, "accuracy": v.accuracy, "f1": v.f1, "status": v.status}
            for v in versions
        ],
        "recent_failures": [
            {"node": e.node_id, "message": e.message, "at": e.created_at.isoformat()} for e in failed_events
        ],
        "algorithms": {alg: sum(1 for j in jobs if j.algorithm == alg) for alg in ("fedavg", "fedprox", "fedadam")},
    }


def _rule_based_answer(question: str, ctx: dict) -> str:
    q = question.lower()
    if any(w in q for w in ["round", "current"]):
        r = ctx["latest_round"]
        if not r:
            return "No rounds have been executed yet. Create a training job in the Training Center and start it to see federated rounds."
        return (
            f"The latest completed round is round {r['number']} with global accuracy {r['accuracy']*100:.1f}% "
            f"(loss {r['loss']:.4f}), with {r['participated']} clients participating. "
            f"{ctx['rounds']} rounds have run in total across {ctx['jobs']} jobs."
        )
    if any(w in q for w in ["version", "compare", "model"]):
        if not ctx["versions"]:
            return "No model versions exist yet. Complete a training job to generate a version."
        best = max(ctx["versions"], key=lambda v: v["f1"] or 0)
        lines = [f"v{v['version']} (job {v['job_id']}): accuracy {v['accuracy']*100:.1f}%, F1 {v['f1']:.3f}, status {v['status']}" for v in ctx["versions"]]
        return f"There are {len(ctx['versions'])} model versions.\n" + "\n".join(lines) + f"\nBest: v{best['version']} with F1 {best['f1']:.3f}."
    if any(w in q for w in ["contribut", "client", "node"]):
        return (
            "Client contribution is tracked per round. Every participating node contributes masked weight "
            "deltas; contribution scores are derived from local validation accuracy and participation count. "
            "Open Analytics → Node Contribution to see the ranked leaderboard."
        )
    if any(w in q for w in ["fail", "error", "offline"]):
        if not ctx["recent_failures"]:
            return "No communication failures detected recently. All nodes are synchronized."
        return "Recent failure events:\n" + "\n".join(f"- Node {e['node']}: {e['message']} ({e['at']})" for e in ctx["recent_failures"])
    if any(w in q for w in ["hyperparameter", "tune", "improve", "lr", "learning rate"]):
        return (
            "Recommended hyperparameter direction: for faster convergence try learning_rate 0.01–0.05 with "
            "local_epochs 2–3; for heterogeneous data prefer FedProx with mu 0.01–0.1; for larger node counts "
            "raise client_fraction to 0.6–0.8. Watch the Communication Monitor for round latency when raising epochs."
        )
    if any(w in q for w in ["privacy", "secure", "encrypt"]):
        return (
            "All client updates are masked with Bonawitz-style pairwise masks, signed with node RSA keys "
            f"(mTLS), and encrypted with AES-256-GCM. Privacy budget consumed: track via Analytics → Privacy Metrics."
        )
    if any(w in q for w in ["accuracy", "explain", "performance", "metric"]):
        if not ctx["versions"]:
            return "No evaluation data yet."
        accs = [v["accuracy"] or 0 for v in ctx["versions"]]
        return f"Average model accuracy across {len(ctx['versions'])} versions is {sum(accs)/len(accs)*100:.1f}%. See Evaluation for per-version precision/recall/F1."
    return (
        "I can help with: current federated rounds, model version comparison, accuracy explanation, "
        "client contribution analysis, communication failures, training summaries, and hyperparameter "
        "recommendations. Ask one of those to get a data-backed answer."
    )


def _llm_answer(provider: AIProvider, question: str, ctx: dict) -> tuple[str, int, int]:
    from app.ai.providers import chat_completion

    system = (
        "You are the AI assistant for an enterprise federated learning platform. "
        "Answer concisely using ONLY the provided platform context. "
        "Be precise and cite actual numbers from the context when available.\n\n"
        f"Platform context:\n{json.dumps(ctx, default=str)}"
    )
    start = time.time()
    result = chat_completion(
        provider.provider_type,
        provider.base_url or "https://api.openai.com/v1",
        decrypt_secret(provider.api_key_encrypted),
        provider.models[0] if provider.models else "",
        [{"role": "system", "content": system}, {"role": "user", "content": question}],
        temperature=0.2,
    )
    latency = int((time.time() - start) * 1000)
    return result["content"], result.get("tokens", 0), latency


@router.post("/ask", response_model=ChatResponse)
def ask(
    body: ChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.USE_AI)),
):
    ctx = _platform_context(db)
    provider = db.get(AIProvider, body.provider_id) if body.provider_id else db.query(AIProvider).filter(AIProvider.status == "tested").first()

    question = body.messages[-1]["content"] if body.messages else ""
    start = time.time()

    if provider and provider.api_key_encrypted and provider.models:
        try:
            content, tokens, latency = _llm_answer(provider, question, ctx)
            status = "ok"
            error = ""
            db.add(
                InferenceLog(
                    provider_id=provider.id, provider_name=provider.name,
                    model=provider.models[0], prompt_preview=question[:120],
                    response_preview=content[:120], latency_ms=latency, tokens=tokens,
                    status="ok", created_by=user.id,
                )
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001
            content = _rule_based_answer(question, ctx)
            status = "fallback"
            error = str(exc)[:200]
            latency = int((time.time() - start) * 1000)
    else:
        content = _rule_based_answer(question, ctx)
        status = "rule_based"
        error = ""
        latency = int((time.time() - start) * 1000)

    return ChatResponse(
        provider_id=provider.id if provider else 0,
        provider_name=provider.name if provider else "Built-in rule engine",
        model=provider.models[0] if provider and provider.models else "rule-based",
        content=content,
        tokens=0,
        latency_ms=latency,
        status=status,
        error=error,
    )
