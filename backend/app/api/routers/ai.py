"""AI Integrations module.

Bring-your-own-key: API keys are AES-256 encrypted at rest, masked on display,
and only admins can manage providers. Includes Prompt Studio and Inference Logs.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_client_ip, require_permission
from app.core.audit import write_audit
from app.core.database import get_db
from app.core.rbac import Permission
from app.core.security import decrypt_secret, encrypt_secret, mask_key
from app.models.models import AIProvider, InferenceLog, PromptTemplate, User
from app.schemas.schemas import (
    ChatRequest,
    ChatResponse,
    MessageOut,
    PromptTemplateCreate,
    PromptTemplateOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)

router = APIRouter(prefix="/ai", tags=["ai"])

admin_guard = require_permission(Permission.MANAGE_AI)
use_guard = require_permission(Permission.USE_AI)


def _provider_out(p: AIProvider) -> ProviderOut:
    return ProviderOut.model_validate(p)


@router.get("/specs", response_model=list[dict])
def provider_specs(user: User = Depends(use_guard)):
    from app.ai.providers import provider_specs_public

    return provider_specs_public()


@router.get("/providers", response_model=list[ProviderOut])
def list_providers(db: Session = Depends(get_db), user: User = Depends(admin_guard)):
    return [_provider_out(p) for p in db.query(AIProvider).order_by(AIProvider.name).all()]


@router.get("/providers/available", response_model=list[ProviderOut])
def list_available_providers(db: Session = Depends(get_db), user: User = Depends(use_guard)):
    """Providers usable by non-admin roles for chat/inference (masked)."""
    return [_provider_out(p) for p in db.query(AIProvider).filter(AIProvider.status != "unreachable").all()]


@router.post("/providers", response_model=ProviderOut)
def create_provider(
    body: ProviderCreate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(admin_guard),
):
    from app.ai.providers import SPEC_MAP

    if body.provider_type not in SPEC_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown provider type '{body.provider_type}'")
    spec = SPEC_MAP[body.provider_type]
    base_url = body.base_url or spec.default_base_url
    models = body.models or spec.default_models
    encrypted = encrypt_secret(body.api_key) if body.api_key else ""
    provider = AIProvider(
        name=body.name or spec.label,
        provider_type=body.provider_type,
        base_url=base_url,
        api_key_encrypted=encrypted,
        key_mask=mask_key(body.api_key) if body.api_key else "",
        models=models,
        temperature_default=body.temperature_default,
        status="configured",
        created_by=user.id,
    )
    db.add(provider)
    db.commit()
    db.refresh(provider)
    write_audit(db, action="ai.provider.create", entity_type="ai_provider", entity_id=provider.id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"provider": provider.provider_type})
    return _provider_out(provider)


@router.put("/providers/{provider_id}", response_model=ProviderOut)
def update_provider(
    provider_id: int,
    body: ProviderUpdate,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(admin_guard),
):
    provider = db.get(AIProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    updates = body.model_dump(exclude_unset=True)
    if "api_key" in updates and updates["api_key"]:
        provider.api_key_encrypted = encrypt_secret(updates["api_key"])
        provider.key_mask = mask_key(updates["api_key"])
    for field in ("name", "base_url", "models", "temperature_default"):
        if field in updates and updates[field] is not None:
            setattr(provider, field, updates[field])
    db.commit()
    db.refresh(provider)
    write_audit(db, action="ai.provider.update", entity_type="ai_provider", entity_id=provider_id,
                actor_id=user.id, actor_email=user.email, ip=ip)
    return _provider_out(provider)


@router.post("/providers/{provider_id}/test", response_model=dict)
def test_connection(
    provider_id: int,
    ip: str = Depends(get_client_ip),
    db: Session = Depends(get_db),
    user: User = Depends(admin_guard),
):
    provider = db.get(AIProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not provider.api_key_encrypted:
        return {"ok": False, "message": "No API key configured", "latency_ms": 0}
    from app.ai.providers import test_provider

    result = test_provider(
        provider.provider_type, provider.base_url, decrypt_secret(provider.api_key_encrypted),
        provider.models[0] if provider.models else "",
    )
    provider.status = "tested" if result["ok"] else "unreachable"
    provider.latency_ms = result.get("latency_ms", 0)
    db.commit()
    write_audit(db, action="ai.provider.test", entity_type="ai_provider", entity_id=provider_id,
                actor_id=user.id, actor_email=user.email, ip=ip,
                details={"ok": result["ok"]})
    return result


@router.delete("/providers/{provider_id}", response_model=MessageOut)
def delete_provider(provider_id: int, db: Session = Depends(get_db), user: User = Depends(admin_guard)):
    provider = db.get(AIProvider, provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    write_audit(db, action="ai.provider.delete", entity_type="ai_provider", entity_id=provider_id,
                actor_id=user.id, actor_email=user.email, severity="warning")
    return MessageOut(message="Provider deleted")


@router.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(use_guard)):
    import time

    from app.ai.providers import chat_completion

    provider = db.get(AIProvider, body.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    if not provider.api_key_encrypted and provider.provider_type != "ollama":
        raise HTTPException(status_code=400, detail="Provider has no API key configured")
    model = body.model or (provider.models[0] if provider.models else "")
    if not model:
        raise HTTPException(status_code=400, detail="No model selected")
    start = time.time()
    try:
        result = chat_completion(
            provider.provider_type,
            provider.base_url,
            decrypt_secret(provider.api_key_encrypted) if provider.api_key_encrypted else "",
            model,
            body.messages,
            body.temperature if body.temperature is not None else provider.temperature_default,
        )
        latency = int((time.time() - start) * 1000)
        db.add(
            InferenceLog(
                provider_id=provider.id, provider_name=provider.name, model=model,
                prompt_preview=(body.messages[-1].get("content", "") if body.messages else "")[:120],
                response_preview=result["content"][:120], latency_ms=latency,
                tokens=result.get("tokens", 0), status="ok", created_by=user.id,
            )
        )
        db.commit()
        return ChatResponse(
            provider_id=provider.id, provider_name=provider.name, model=model,
            content=result["content"], tokens=result.get("tokens", 0),
            latency_ms=latency, status="ok",
        )
    except Exception as exc:  # noqa: BLE001
        latency = int((time.time() - start) * 1000)
        db.add(
            InferenceLog(
                provider_id=provider.id, provider_name=provider.name, model=model,
                prompt_preview=(body.messages[-1].get("content", "") if body.messages else "")[:120],
                latency_ms=latency, status="error", error=str(exc)[:300], created_by=user.id,
            )
        )
        db.commit()
        return ChatResponse(
            provider_id=provider.id, provider_name=provider.name, model=model,
            content="", tokens=0, latency_ms=latency, status="error", error=str(exc)[:300],
        )


# ------------------------------------------------------------ prompt studio
@router.get("/prompts", response_model=list[PromptTemplateOut])
def list_prompts(db: Session = Depends(get_db), user: User = Depends(use_guard)):
    return [PromptTemplateOut.model_validate(p) for p in db.query(PromptTemplate).order_by(PromptTemplate.name).all()]


@router.post("/prompts", response_model=PromptTemplateOut)
def create_prompt(body: PromptTemplateCreate, db: Session = Depends(get_db), user: User = Depends(use_guard)):
    p = PromptTemplate(
        name=body.name, provider_id=body.provider_id, model=body.model,
        system_prompt=body.system_prompt, user_prompt=body.user_prompt,
        temperature=body.temperature, variables=body.variables, created_by=user.id,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return PromptTemplateOut.model_validate(p)


@router.delete("/prompts/{prompt_id}", response_model=MessageOut)
def delete_prompt(prompt_id: int, db: Session = Depends(get_db), user: User = Depends(use_guard)):
    p = db.get(PromptTemplate, prompt_id)
    if p is None:
        raise HTTPException(status_code=404, detail="Prompt not found")
    db.delete(p)
    db.commit()
    return MessageOut(message="Prompt deleted")


@router.get("/inference-logs", response_model=list[dict])
def inference_logs(
    limit: int = Query(50),
    provider_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(use_guard),
):
    query = db.query(InferenceLog)
    if provider_id:
        query = query.filter(InferenceLog.provider_id == provider_id)
    logs = query.order_by(InferenceLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id, "provider_id": l.provider_id, "provider_name": l.provider_name,
            "model": l.model, "prompt_preview": l.prompt_preview,
            "response_preview": l.response_preview, "latency_ms": l.latency_ms,
            "tokens": l.tokens, "status": l.status, "error": l.error,
            "created_at": l.created_at,
        }
        for l in logs
    ]
