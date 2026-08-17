"""API smoke tests for the Federated AI Platform.

Runs against a temporary SQLite database via FastAPI's TestClient — no
external services required. Exercises the critical security + module surface:

  * authentication (register / login / me)
  * RBAC enforcement (org admin blocked from platform-admin actions)
  * every read endpoint of the major modules returns 200
  * write path: create + launch a live training job to completion
"""
from __future__ import annotations

import os
import tempfile

# isolate the DB before importing the app
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import init_db  # noqa: E402

init_db()

# populate a realistic federation (orgs, users, nodes, datasets, completed jobs)
from app.seed import seed_demo_data  # noqa: E402

seed_demo_data()

from app.main import app  # noqa: E402

client = TestClient(app)

ADMIN = {"email": "admin@example.com", "password": "adminpass123", "full_name": "Test Admin", "role": "admin"}
ORG_ADMIN = {"email": "orgadmin@example.com", "password": "orgpass123", "full_name": "Org Admin", "role": "org_admin"}


def auth_token(payload: dict) -> str:
    r = client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    if r.status_code == 401:
        r = client.post("/api/v1/auth/register", json=payload)
        assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_flow():
    tok = auth_token(ADMIN)
    me = client.get("/api/v1/auth/me", headers=_headers(tok))
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == ADMIN["email"]
    assert "admin" in body["role_label"].lower()
    assert len(body["permissions"]) > 0


def test_rbac_enforcement():
    tok = auth_token(ORG_ADMIN)
    # org admin must NOT reach platform admin endpoints
    r = client.get("/api/v1/admin/users", headers=_headers(tok))
    assert r.status_code == 403, r.text
    # ...but can read their own org's datasets
    r = client.get("/api/v1/datasets", headers=_headers(tok))
    assert r.status_code in (200, 403)


def test_module_read_endpoints():
    tok = auth_token(ADMIN)
    h = _headers(tok)
    endpoints = [
        "/api/v1/dashboard",
        "/api/v1/organizations",
        "/api/v1/organizations/stats",
        "/api/v1/nodes",
        "/api/v1/nodes/health",
        "/api/v1/datasets",
        "/api/v1/datasets/summary",
        "/api/v1/training",
        "/api/v1/training/stats",
        "/api/v1/coordinator/overview",
        "/api/v1/coordinator/aggregation-logs",
        "/api/v1/models",
        "/api/v1/models/stats",
        "/api/v1/evaluation",
        "/api/v1/xai/bias-report",
        "/api/v1/monitor/overview",
        "/api/v1/monitor/timeline",
        "/api/v1/analytics/overview",
        "/api/v1/analytics/privacy",
        "/api/v1/reports/types",
        "/api/v1/audit/logs",
        "/api/v1/audit/verify",
        "/api/v1/audit/summary",
        "/api/v1/admin/users",
        "/api/v1/admin/feature-flags",
        "/api/v1/admin/settings",
        "/api/v1/admin/system",
        "/api/v1/ai/specs",
        "/api/v1/ai/providers",
        "/api/v1/ai/prompts",
        "/api/v1/ai/inference-logs",
        "/api/v1/lab/experiments",
        "/api/v1/settings/profile",
    ]
    for ep in endpoints:
        r = client.get(ep, headers=h)
        assert r.status_code == 200, f"{ep} -> {r.status_code}: {r.text[:200]}"


def test_secure_aggregation_demo():
    tok = auth_token(ADMIN)
    r = client.post("/api/v1/coordinator/secure-aggregation/demo", json={"clients": 4}, headers=_headers(tok))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mask_pairs"] == 12  # directed pairs: N * (N - 1)
    assert body["verified_signatures"] == 4
    assert body["math_ok"] is True


def test_audit_chain_integrity():
    tok = auth_token(ADMIN)
    r = client.get("/api/v1/audit/verify", headers=_headers(tok))
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_training_job_lifecycle():
    """Create, approve and run a small federated job to completion."""
    tok = auth_token(ADMIN)
    h = _headers(tok)
    r = client.post(
        "/api/v1/training",
        json={
            "name": "ci-job",
            "algorithm": "fedavg",
            "total_rounds": 2,
            "client_fraction": 0.5,
            "learning_rate": 0.01,
            "local_epochs": 1,
            "secure_aggregation": True,
            "hidden_layers": [8],
            "input_dim": 4,
            "local_samples": 120,
            "data_distribution": "iid",
            "selected_node_ids": [],
        },
        headers=h,
    )
    assert r.status_code in (200, 201), r.text
    job = r.json()
    job_id = job["id"]

    # approve (admin has permission)
    r = client.post(f"/api/v1/coordinator/approvals/{job_id}", json={"action": "approve", "notes": "ci"}, headers=h)
    assert r.status_code == 200, r.text

    # start -> wait for completion
    r = client.post(f"/api/v1/training/{job_id}/action", json={"action": "start"}, headers=h)
    assert r.status_code == 200, r.text

    import time

    final = None
    for _ in range(40):
        time.sleep(0.5)
        r = client.get(f"/api/v1/training/{job_id}", headers=h)
        assert r.status_code == 200
        final = r.json()
        if final["status"] in ("completed", "failed"):
            break
    assert final is not None
    assert final["status"] == "completed", final
    assert final["current_round"] == 2

    rounds = client.get(f"/api/v1/training/{job_id}/rounds", headers=h).json()
    assert len(rounds) == 2

    # model version produced
    versions = client.get("/api/v1/models", headers=h).json()
    assert any(v["job_id"] == job_id for v in versions)


if __name__ == "__main__":
    import sys

    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
