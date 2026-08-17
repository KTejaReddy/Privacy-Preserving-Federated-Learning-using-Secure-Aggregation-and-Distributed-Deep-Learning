"""Explainable AI Center: SHAP-style explanations, importance, fairness, bias."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.database import get_db
from app.core.rbac import Permission
from app.explainability.xai import XAIEngine
from app.federated.engine import build_mlp
from app.models.models import FederatedNode, ModelVersion, TrainingJob, User

router = APIRouter(prefix="/xai", tags=["explainability"])


def _load_model(db: Session, version_id: int):
    import numpy as np

    v = db.get(ModelVersion, version_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Version not found")
    job = db.get(TrainingJob, v.job_id)
    names = (v.metrics_json or {}).get("feature_names")
    input_dim = len(names) if names else int((job.metrics_json or {}).get("input_dim", 8))
    layers = job.hidden_layers or [16, 8]
    model = build_mlp(input_dim, layers, seed=42)
    weights = np.array((v.metrics_json or {}).get("weights", []))
    if weights.size:
        model.load_flattened(weights)
    else:
        from app.federated.data import generate_non_iid_node_data

        X, y = generate_non_iid_node_data(42, 99, 400, input_dim, "iid", noise=0.1)
        model.train(X, y, epochs=1, batch_size=64, lr=0.01)
    feature_names_list = names or [f"feature_{i}" for i in range(input_dim)]
    return v, job, model, feature_names_list


@router.get("/explain", response_model=dict)
def explain_sample(
    version_id: int = Query(...),
    sample_index: int = Query(0),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_XAI)),
):
    import numpy as np

    from app.federated.data import generate_non_iid_node_data

    v, job, model, names = _load_model(db, version_id)
    X, y = generate_non_iid_node_data(42, 99, 500, len(names), "iid", noise=0.1)
    engine = XAIEngine(model.predict_proba, names)
    x = X[sample_index % len(X)]
    result = engine.local_explanation(x, X, nsamples=256)
    result["sample_index"] = sample_index % len(X)
    result["true_label"] = int(y[sample_index % len(X)])
    result["model_version_id"] = version_id
    return result


@router.get("/importance", response_model=dict)
def feature_importance(
    version_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_XAI)),
):
    import numpy as np

    from app.federated.data import generate_non_iid_node_data

    v, job, model, names = _load_model(db, version_id)
    X, y = generate_non_iid_node_data(42, 99, 600, len(names), "iid", noise=0.1)
    engine = XAIEngine(model.predict_proba, names)
    return engine.global_importance(X, y)


@router.get("/fairness", response_model=dict)
def fairness_analysis(
    version_id: int = Query(...),
    sensitive_feature: str = Query("feature_0"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_XAI)),
):
    import numpy as np

    from app.federated.data import generate_non_iid_node_data

    v, job, model, names = _load_model(db, version_id)
    if sensitive_feature not in names and sensitive_feature != "feature_0":
        raise HTTPException(status_code=400, detail=f"Unknown feature '{sensitive_feature}'")
    idx = names.index(sensitive_feature) if sensitive_feature in names else 0
    X, y = generate_non_iid_node_data(42, 99, 800, len(names), "iid", noise=0.1)
    # binarize the sensitive attribute (above median = group_1)
    threshold = float(np.median(X[:, idx]))
    Xs = X.copy()
    Xs[:, idx] = (Xs[:, idx] >= threshold).astype(int)
    engine = XAIEngine(model.predict_proba, names)
    return engine.fairness_analysis(Xs, y, sensitive_idx=idx, sensitive_labels=["below_median", "above_median"])


@router.get("/compare", response_model=dict)
def compare_models(
    version_ids: str = Query(..., description="comma-separated"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(Permission.VIEW_XAI)),
):
    versions = []
    for vid in [int(x) for x in version_ids.split(",") if x.strip()]:
        v = db.get(ModelVersion, vid)
        if v:
            versions.append(
                {
                    "version": v.version,
                    "accuracy": v.accuracy,
                    "precision": v.precision,
                    "recall": v.recall,
                    "f1": v.f1,
                    "status": v.status,
                }
            )
    if not versions:
        raise HTTPException(status_code=400, detail="No valid versions")
    best = max(versions, key=lambda r: (r.get("f1") or 0))
    return {"versions": versions, "best_version": best}


@router.get("/bias-report", response_model=dict)
def bias_report(db: Session = Depends(get_db), user: User = Depends(require_permission(Permission.VIEW_XAI))):
    """Aggregate bias/fairness across all evaluated versions."""
    import numpy as np

    from app.federated.data import generate_non_iid_node_data

    versions = db.query(ModelVersion).filter(ModelVersion.f1.isnot(None)).order_by(ModelVersion.id.desc()).limit(6).all()
    reports = []
    for v in versions:
        job = db.get(TrainingJob, v.job_id)
        names = (v.metrics_json or {}).get("feature_names") or [f"feature_{i}" for i in range(8)]
        input_dim = len(names)
        layers = job.hidden_layers or [16, 8]
        model = build_mlp(input_dim, layers, seed=42)
        X, y = generate_non_iid_node_data(42, 99, 600, input_dim, "iid", noise=0.1)
        model.train(X, y, epochs=1, batch_size=64, lr=0.01)
        engine = XAIEngine(model.predict_proba, names)
        idx = 0
        Xs = X.copy()
        Xs[:, idx] = (Xs[:, idx] >= np.median(Xs[:, idx])).astype(int)
        f = engine.fairness_analysis(Xs, y, sensitive_idx=idx)
        reports.append({"version": v.version, "bias_level": f["bias_level"], "demographic_parity": f["demographic_parity"],
                        "equalized_odds": f["equalized_odds"], "disparate_impact": f["disparate_impact"]})
    return {"reports": reports, "healthy": sum(1 for r in reports if r["bias_level"] == "low"),
            "attention": sum(1 for r in reports if r["bias_level"] == "high")}
