"""Synthetic data generation for the federated platform.

Each organization's dataset is represented by metadata; the engine synthesizes
the actual feature matrix deterministically (seeded per organization) so that
"local" data never leaves the organization and every run is reproducible.

Non-IID data is simulated via per-client covariate shift: the ground-truth
decision boundary is rotated/shifted for each client, which is exactly the
real-world scenario that makes federated aggregation meaningful.
"""
from __future__ import annotations

from typing import List, Tuple

import numpy as np

DEFAULT_FEATURE_NAMES = [
    "account_age",
    "balance",
    "transactions",
    "credit_score",
    "risk_factor",
    "engagement",
    "geo_density",
    "support_tickets",
]


def feature_names(feature_count: int) -> List[str]:
    if feature_count == len(DEFAULT_FEATURE_NAMES):
        return list(DEFAULT_FEATURE_NAMES)
    return [f"feature_{i}" for i in range(feature_count)]


def generate_classification(
    n_samples: int,
    n_features: int,
    positive_ratio: float = 0.5,
    noise: float = 0.15,
    seed: int = 0,
    boundary_shift: float = 0.0,
    signal: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a binary classification dataset with a linear decision boundary.

    `signal` scales the logits so the classes are learnable (sigmoid saturation);
    `noise` flips a fraction of labels after sampling.
    """
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_samples, n_features))
    w = rng.standard_normal(n_features)
    w = w / (np.linalg.norm(w) + 1e-9)
    logits = (X @ w + boundary_shift) * signal
    # calibrate to requested positive ratio
    threshold = np.quantile(logits, 1.0 - positive_ratio)
    p = 1.0 / (1.0 + np.exp(-(logits - threshold)))
    y = (rng.random(n_samples) < p).astype(int)
    if noise > 0:
        flip = rng.random(n_samples) < noise
        y[flip] = 1 - y[flip]
    return X, y


def generate_dataset(meta: dict, seed: int) -> Tuple[np.ndarray, np.ndarray]:
    """Generate a dataset from registry metadata."""
    n = int(meta.get("sample_count", 1000))
    f = int(meta.get("feature_count", 8))
    ratio = float(meta.get("positive_ratio", 0.5))
    noise = float(meta.get("noise", 0.15))
    shift = float(meta.get("boundary_shift", 0.0))
    return generate_classification(n, f, ratio, noise, seed=seed, boundary_shift=shift)


def _generate_with_w(
    n_samples: int,
    n_features: int,
    w_base: np.ndarray,
    boundary_shift: float,
    noise: float,
    seed: int,
    positive_ratio: float = 0.5,
) -> Tuple[np.ndarray, np.ndarray]:
    """Generate labels from a *shared* ground-truth weight vector.

    All nodes (and the global evaluation set) learn the same underlying task;
    `boundary_shift` and rotation only change the observed data distribution.
    """
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n_samples, n_features))
    logits = (X @ w_base + boundary_shift) * 2.0
    threshold = np.quantile(logits, 1.0 - positive_ratio)
    p = 1.0 / (1.0 + np.exp(-(logits - threshold)))
    y = (rng.random(n_samples) < p).astype(int)
    if noise > 0:
        flip = rng.random(n_samples) < noise
        y[flip] = 1 - y[flip]
    return X, y


def generate_non_iid_node_data(
    global_seed: int,
    node_index: int,
    n_samples: int,
    n_features: int,
    distribution: str = "iid",
    noise: float = 0.15,
) -> Tuple[np.ndarray, np.ndarray]:
    """Per-node data partition sharing one global task. `distribution` controls
    statistical heterogeneity:

    - iid:          identical distribution across nodes.
    - non_iid:      covariate shift (label-boundary threshold + feature rotation).
    - pathological: each node only sees a biased slice of the classes (label skew).
    """
    rng_base = np.random.default_rng(global_seed)
    w_base = rng_base.standard_normal(n_features)
    w_base = w_base / (np.linalg.norm(w_base) + 1e-9)

    if distribution == "pathological":
        ratio = 0.9 if node_index % 2 == 0 else 0.1
        return _generate_with_w(n_samples, n_features, w_base, 0.0, noise, seed=global_seed + node_index, positive_ratio=ratio)

    if distribution == "non_iid":
        shift = (node_index - 4) * 0.15
        X, y = _generate_with_w(n_samples, n_features, w_base, shift, noise, seed=global_seed + node_index)
        # mild rotation of the first two features (boundary stays learnable)
        rot = np.eye(n_features)
        if n_features >= 2:
            a = 0.3 + 0.15 * node_index
            c, s = np.cos(a), np.sin(a)
            rot[0, 0], rot[0, 1], rot[1, 0], rot[1, 1] = c, -s, s, c
        return X @ rot, y

    return _generate_with_w(n_samples, n_features, w_base, 0.0, noise, seed=global_seed + node_index)


def evaluate(model, X: np.ndarray, y: np.ndarray) -> dict:
    """Full classification metrics for a model on a dataset."""
    from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score

    proba = model.predict_proba(X)
    preds = proba.argmax(axis=1)
    n_classes = len(np.unique(y))
    if n_classes == 2 and proba.shape[1] == 2:
        auc = float(roc_auc_score(y, proba[:, 1]))
    else:
        auc = float(roc_auc_score(y, proba, multi_class="ovr", average="macro"))
    return {
        "accuracy": round(float(accuracy_score(y, preds)), 4),
        "precision": round(float(precision_score(y, preds, zero_division=0)), 4),
        "recall": round(float(recall_score(y, preds, zero_division=0)), 4),
        "f1": round(float(f1_score(y, preds, zero_division=0)), 4),
        "auc": round(auc, 4),
    }
