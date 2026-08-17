"""Immutable (append-only) audit logging.

Every sensitive action is written to the AuditLog table. A SHA-256 hash chain
links each record to its predecessor, making tampering detectable.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.models import AuditLog


def _compute_chain_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{payload}".encode("utf-8")).hexdigest()


def _canonical_payload(action: str, entity_type: str, entity_id: Any, details: dict) -> str:
    """Single canonical serialization used by BOTH write and verify so the
    chain can never diverge between the two paths."""
    return json.dumps(
        {
            "action": action,
            "entity": entity_type,
            "entity_id": str(entity_id) if entity_id is not None else None,
            "details": details or {},
        },
        sort_keys=True,
        default=str,
    )


def write_audit(
    db: Session,
    action: str,
    entity_type: str = "",
    entity_id: Any = None,
    details: Optional[dict] = None,
    actor_id: Optional[int] = None,
    actor_email: str = "system",
    ip: str = "",
    severity: str = "info",
) -> AuditLog:
    """Write an audit record, chaining it to the previous record."""
    last = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last.chain_hash if last else "GENESIS"
    chain_hash = _compute_chain_hash(prev_hash, _canonical_payload(action, entity_type, entity_id, details or {}))
    record = AuditLog(
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
        ip=ip,
        severity=severity,
        chain_hash=chain_hash,
        previous_hash=prev_hash,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def verify_chain(db: Session) -> tuple[bool, str]:
    """Verify hash-chain integrity of the entire audit log."""
    records = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    prev = "GENESIS"
    for r in records:
        payload = _canonical_payload(r.action, r.entity_type, r.entity_id, r.details or {})
        expected = _compute_chain_hash(prev, payload)
        if r.chain_hash != expected:
            return False, f"Tampering detected at audit record #{r.id}"
        prev = r.chain_hash
    return True, f"Chain intact: {len(records)} records verified"
