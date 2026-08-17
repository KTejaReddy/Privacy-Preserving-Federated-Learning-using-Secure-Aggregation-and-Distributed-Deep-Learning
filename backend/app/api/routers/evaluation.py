"""Model Evaluation Center: metrics, comparisons and regression tracking."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.models.models import FederatedRound, ModelVersion, TrainingJob, User

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("", response_model=dict)
def evaluation_summary(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_EVALUATION))):
    versions = db.query(ModelVersion).order_by(ModelVersion.created_at).all()
    rounds = db.query(FederatedRound).order_by(FederatedRound.round_number).all()
    return {
        "best_accuracy": max((v.accuracy or 0 for v in versions), default=0),
        "best_f1": max((v.f1 or 0 for v in versions), default=0),
        "average_precision": round(sum(v.precision or 0 for v in versions) / max(len(versions), 1), 4),
        "average_recall": round(sum(v.recall or 0 for v in versions) / max(len(versions), 1), 4),
        "version_count": len(versions),
        "round_count": len(rounds),
        "accuracy_history": [
            {"version": v.version, "job_id": v.job_id, "accuracy": v.accuracy, "f1": v.f1, "status": v.status}
            for v in versions
        ],
    }


@router.get("/compare", response_model=dict)
def compare_versions(
    version_ids: str = Query(..., description="comma-separated version ids"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_EVALUATION)),
):
    ids = [int(x) for x in version_ids.split(",") if x.strip()]
    rows = []
    for vid in ids:
        v = db.get(ModelVersion, vid)
        if v:
            job = db.get(TrainingJob, v.job_id)
            rows.append(
                {
                    "id": v.id,
                    "version": v.version,
                    "job": job.name if job else f"job-{v.job_id}",
                    "algorithm": job.algorithm if job else "—",
                    "accuracy": v.accuracy,
                    "precision": v.precision,
                    "recall": v.recall,
                    "f1": v.f1,
                    "status": v.status,
                }
            )
    best = max(rows, key=lambda r: (r.get("f1") or 0), default=None)
    return {"rows": rows, "best": best}


@router.get("/confusion/{version_id}", response_model=dict)
def confusion_matrix(version_id: int, db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_EVALUATION))):
    """Reconstruct a confusion matrix for a version using its metrics + a
    synthetic reference evaluation (deterministic)."""
    v = db.get(ModelVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")

    import numpy as np

    from app.federated.data import evaluate, generate_non_iid_node_data
    from app.federated.engine import build_mlp

    input_dim, layers = 8, [16, 8]
    names = (v.metrics_json or {}).get("feature_names")
    if names:
        input_dim = len(names)
    layers = db.get(TrainingJob, v.job_id).hidden_layers or [16, 8]

    model = build_mlp(input_dim, layers, seed=42)
    weights = np.array((v.metrics_json or {}).get("weights", []))
    if weights.size:
        model.load_flattened(weights)
    else:
        X, y = generate_non_iid_node_data(42, 99, 400, input_dim, "iid", noise=0.1)
        model.train(X, y, epochs=1, batch_size=64, lr=0.01)
    X, y = generate_non_iid_node_data(42, 7, 600, input_dim, "iid", noise=0.1)
    preds = model.predict(X)
    tp = int(((preds == 1) & (y == 1)).sum())
    tn = int(((preds == 0) & (y == 0)).sum())
    fp = int(((preds == 1) & (y == 0)).sum())
    fn = int(((preds == 0) & (y == 1)).sum())
    return {
        "matrix": [[tp, fn], [fp, tn]],
        "labels": ["predicted positive", "predicted negative"],
        "metrics": evaluate(model, X, y),
    }
