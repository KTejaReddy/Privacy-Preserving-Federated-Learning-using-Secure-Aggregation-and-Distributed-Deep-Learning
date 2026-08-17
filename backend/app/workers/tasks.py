"""Background task definitions.

- execute_training_job: runs the federated engine and persists round results.
- simulate_node_activity: periodic node heartbeat + event feed for the monitor.

These are registered with Celery when FL_USE_CELERY=1; otherwise they are
invoked directly (inline/threaded) by the task queue.
"""
from __future__ import annotations

import json
import random
import threading
import time
from typing import Any, Callable, Dict

from sqlalchemy.orm import Session

from app.core.audit import write_audit
from app.core.events import bus
from app.federated.engine import FederatedEngine
from app.models.models import (
    AggregationLog,
    ClientUpdate,
    Dataset,
    FederatedNode,
    FederatedRound,
    ModelVersion,
    NodeEvent,
    TrainingJob,
)
from app.workers.celery_app import USE_CELERY, celery_app

if USE_CELERY and celery_app is not None:
    celery_task = celery_app.task
else:

    def celery_task(*args, **kwargs):  # type: ignore
        """Fallback decorator: mimics Celery's `bind=True` by dropping the
        injected `self` argument so task call sites are identical either way."""
        bind = bool(kwargs.get("bind", False))

        def _decorate(fn):
            if bind:

                def _wrapper(_self, *a, **k):
                    return fn(*a, **k)

                return _wrapper
            return fn

        if len(args) == 1 and callable(args[0]):
            return args[0]
        return _decorate


def _node_dict(n: FederatedNode) -> dict:
    return {"id": n.id, "name": n.name, "status": n.status, "trust_score": n.trust_score}


def _dataset_dict(d: Dataset) -> dict:
    return {
        "organization_id": d.organization_id,
        "feature_count": d.feature_count,
        "sample_count": d.sample_count,
        "noise": d.noise,
        "positive_ratio": d.positive_ratio,
    }


def _emit(round_number: int, t: str, payload: dict) -> None:
    bus.publish("federated", {"round": round_number, "type": t, "payload": payload})
    bus.publish(t, {"round": round_number, **payload})


@celery_task(name="app.workers.tasks.execute_training_job")
def execute_training_job(job_id: int) -> dict:
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        job = db.get(TrainingJob, job_id)
        if job is None:
            return {"ok": False, "error": "job not found"}
        job.status = "running"
        job.started_at = job.started_at or _now()
        db.commit()

        nodes = [_node_dict(n) for n in db.query(FederatedNode).all() if n.status in ("online", "unknown", "degraded")]
        datasets = [_dataset_dict(d) for d in db.query(Dataset).all()]

        job_cfg = {
            "algorithm": job.algorithm,
            "total_rounds": job.total_rounds,
            "client_fraction": job.client_fraction,
            "learning_rate": job.learning_rate,
            "batch_size": job.batch_size,
            "local_epochs": job.local_epochs,
            "mu": job.mu,
            "server_momentum": job.server_momentum,
            "secure_aggregation": job.secure_aggregation,
            "privacy_budget_per_round": job.privacy_budget_per_round,
            "hidden_layers": job.hidden_layers or [16, 8],
            "input_dim": int(job.metrics_json.get("input_dim", 8)),
            "seed": int(job.metrics_json.get("seed", 42)),
            "local_samples": int(job.metrics_json.get("local_samples", 900)),
            "data_distribution": str(job.metrics_json.get("data_distribution", "non_iid")),
            "noise": float(job.metrics_json.get("noise", 0.15)),
        }

        def on_event(t: str, payload: Dict[str, Any]) -> None:
            _emit(job.current_round + 1, t, payload)

        engine = FederatedEngine()
        result = engine.run_job(job_cfg, nodes, datasets, on_event=on_event)

        # ---- persist rounds
        prev_version = db.query(ModelVersion).filter(ModelVersion.job_id == job.id).order_by(ModelVersion.version.desc()).first()
        next_version = (prev_version.version + 1) if prev_version else 1
        model_version: ModelVersion | None = None

        for i, r in enumerate(result["rounds"]):
            round_rec = FederatedRound(
                job_id=job.id,
                round_number=i + 1,
                status="completed",
                selected_client_ids=[int(cid) for cid in (r.get("client_metrics") or {}).keys()],
                participated_count=r["participated"],
                avg_loss=r["loss"],
                accuracy=r["accuracy"],
                precision=r["precision"],
                recall=r["recall"],
                f1=r["f1"],
                communication_bytes=r["communication_bytes"],
                aggregation_time_ms=r["aggregation_time_ms"],
                client_metrics=r["client_metrics"],
                privacy_budget_used=r["privacy_budget_used"],
                started_at=_now(),
                finished_at=_now(),
            )
            db.add(round_rec)
            db.flush()

            for cid, cmeta in r["client_metrics"].items():
                node = db.get(FederatedNode, int(cid))
                db.add(
                    ClientUpdate(
                        round_id=round_rec.id,
                        node_id=int(cid),
                        status="aggregated",
                        local_accuracy=cmeta.get("accuracy"),
                        local_loss=cmeta.get("loss"),
                        training_time_ms=cmeta.get("training_time_ms", 0),
                        upload_bytes=int(r["communication_bytes"] / max(r["participated"], 1)),
                        contribution_score=round(float(cmeta.get("accuracy", 0)), 4),
                    )
                )

            db.add(
                AggregationLog(
                    round_id=round_rec.id,
                    method=r["agg"].get("method", "masked_sum"),
                    client_count=r["participated"],
                    masked_upload_count=r["participated"] if r["agg"].get("encrypted") else 0,
                    masks_cancelled=bool(r["agg"].get("math_ok")),
                    signature_verified=bool(r["agg"].get("verified", True)),
                    integrity_hash=f"sha256-{job.id}-{i+1}",
                    privacy_budget_consumed=r["privacy_budget_used"],
                    details=r["agg"],
                )
            )
            job.current_round = i + 1
            db.commit()
            bus.publish("round.complete", {"job_id": job.id, "round": i + 1, "accuracy": r["accuracy"]})
            _emit(i + 1, "round.persisted", {"accuracy": r["accuracy"], "loss": r["loss"]})

        # ---- model version
        final = result["rounds"][-1] if result["rounds"] else {}
        model_version = ModelVersion(
            job_id=job.id,
            version=next_version,
            status="pending",
            accuracy=final.get("accuracy"),
            loss=final.get("loss"),
            precision=final.get("precision"),
            recall=final.get("recall"),
            f1=final.get("f1"),
            metrics_json={
                "rounds": result["rounds"],
                "algorithm": result["algorithm"],
                "total_communication_bytes": result["total_communication_bytes"],
                "total_training_time_ms": result["total_training_time_ms"],
                "param_count": result["param_count"],
                "feature_names": result["feature_names"],
                "model_hash": result["model_hash"],
            },
            parent_version=(prev_version.version if prev_version else None),
            created_by=job.created_by,
        )
        db.add(model_version)
        job.status = "completed"
        job.finished_at = _now()
        job.metrics_json = {
            **job.metrics_json,
            "final_accuracy": final.get("accuracy"),
            "final_f1": final.get("f1"),
            "total_communication_bytes": result["total_communication_bytes"],
            "total_training_time_ms": result["total_training_time_ms"],
            "algorithm": result["algorithm"],
        }
        db.commit()
        write_audit(
            db, action="training.completed", entity_type="training_job", entity_id=job.id,
            details={"accuracy": final.get("accuracy"), "version": next_version}, actor_id=job.created_by,
        )
        bus.publish("job.completed", {"job_id": job.id, "accuracy": final.get("accuracy")})
        return {"ok": True, "job_id": job.id, "version": next_version, "accuracy": final.get("accuracy")}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        job = db.get(TrainingJob, job_id)
        if job is not None:
            job.status = "failed"
            job.finished_at = _now()
            db.commit()
        bus.publish("job.failed", {"job_id": job_id, "error": str(exc)})
        return {"ok": False, "job_id": job_id, "error": str(exc)}
    finally:
        db.close()





def _now():
    from app.models.models import utcnow

    return utcnow()


# ---------------------------------------------------------------------------
# Node activity simulator — feeds the realtime Communication Monitor
# ---------------------------------------------------------------------------
_sim_running = False
_sim_lock = threading.Lock()


@celery_task(name="app.workers.tasks.simulate_node_activity")
def simulate_node_activity(ticks: int = 200, interval_s: float = 3.0) -> None:
    """Heartbeat simulation: updates node status + latency and publishes events."""
    global _sim_running
    with _sim_lock:
        if _sim_running:
            return
        _sim_running = True
    try:
        from app.core.database import SessionLocal

        for tick in range(ticks):
            db = SessionLocal()
            try:
                nodes = db.query(FederatedNode).all()
                for n in nodes:
                    rng = random.Random(int(time.time()) + n.id + tick)
                    # mostly stay online, occasional degraded/offline flicker
                    roll = rng.random()
                    if roll < 0.82:
                        n.status = "online"
                    elif roll < 0.92:
                        n.status = "degraded"
                    else:
                        n.status = "offline"
                    n.latency_ms = round(max(4.0, n.latency_ms * (1 + rng.uniform(-0.25, 0.25))), 1)
                    n.last_heartbeat = _now()
                    n.trust_score = round(min(1.0, max(0.5, n.trust_score + rng.uniform(-0.02, 0.02))), 4)
                    if roll >= 0.92:
                        db.add(
                            NodeEvent(
                                node_id=n.id, event_type="failure",
                                message=f"Heartbeat lost for {n.name}", severity="warning",
                            )
                        )
                db.commit()
                bus.publish("monitor.tick", {"tick": tick, "node_count": len(nodes)})
            finally:
                db.close()
            time.sleep(interval_s)
    finally:
        _sim_running = False


def start_simulator(ticks: int = 100000, interval_s: float = 3.0) -> threading.Thread:
    thread = threading.Thread(target=simulate_node_activity, args=(ticks, interval_s), daemon=True)
    thread.start()
    return thread
