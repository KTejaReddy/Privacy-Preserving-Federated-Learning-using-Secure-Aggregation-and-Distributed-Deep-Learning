"""Explainable AI Center.

Implements, in pure NumPy, the core explanation techniques that SHAP/Captum
provide for tabular models:

  - kernel-SHAP style local explanations (additive feature attribution that
    satisfies local accuracy and consistency).
  - global permutation feature importance.
  - confidence scores (calibrated prediction probability).
  - fairness metrics: demographic parity, equalized odds, disparate impact —
    computed over a sensitive attribute.
  - bias detection heuristics with plain-language summaries.
  - human-readable explanation text.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np


class XAIEngine:
    def __init__(self, model_predict_proba, feature_names: List[str], seed: int = 7) -> None:
        self.predict_proba = model_predict_proba
        self.feature_names = feature_names
        self.seed = seed

    # ---------------------------------------------------------------- local
    def local_explanation(self, x: np.ndarray, background: np.ndarray, nsamples: int = 256) -> dict:
        """Kernel-SHAP style explanation for a single sample."""
        rng = np.random.default_rng(self.seed)
        n = len(self.feature_names)
        x = np.asarray(x, dtype=float).reshape(1, -1)
        bg = np.asarray(background, dtype=float)

        # sample subsets S of features (coalitions)
        z = rng.integers(0, 2, size=(nsamples, n)).astype(bool)
        z[0] = True  # full set
        z[1] = False  # empty set

        # build coalition instances: features in S from x, else from background
        bg_samples = bg[rng.integers(0, bg.shape[0], size=nsamples)]
        instances = np.where(z[:, None, :], np.broadcast_to(x, (nsamples, 1, n)),
                             np.broadcast_to(bg_samples[:, None, :], (nsamples, 1, n)))
        proba = self.predict_proba(instances.reshape(nsamples, n))
        fx = proba[:, 1]
        f0 = float(fx[1])  # empty set -> background prediction

        # kernel weights (SHAP kernel)
        size = z.sum(axis=1).astype(float)
        kernel = np.zeros(nsamples)
        for i, s in enumerate(size):
            if s == 0 or s == n:
                kernel[i] = 1e6
            else:
                kernel[i] = (n - 1) / (s * (n - s))
        kernel = kernel / kernel.sum()

        # weighted least squares: fx(S) = phi0 + sum_S phi_i
        Xt = np.hstack([np.ones((nsamples, 1)), z.astype(float)])
        W = np.sqrt(kernel)[:, None]
        Xw, yw = Xt * W, (fx - f0) * W[:, 0]
        try:
            coef, *_ = np.linalg.lstsq(Xw, yw, rcond=None)
        except np.linalg.LinAlgError:
            coef = np.zeros(n + 1)
        phi = coef[1:]

        # confidence
        confidence = float(np.clip(2 * np.abs(proba[0, 1] - 0.5), 0, 1))
        pred_class = int(proba[0].argmax())

        ranked = sorted(
            zip(self.feature_names, phi.tolist()), key=lambda t: abs(t[1]), reverse=True
        )
        text = self._local_text(ranked, pred_class, confidence, x.ravel())
        return {
            "method": "kernel_shap",
            "base_value": round(f0, 4),
            "prediction": round(float(proba[0, 1]), 4),
            "predicted_class": pred_class,
            "confidence": round(confidence, 4),
            "shap_values": [round(float(v), 4) for v in phi],
            "feature_names": self.feature_names,
            "ranked_contributions": [
                {"feature": f, "shap": round(float(v), 4), "direction": "positive" if v >= 0 else "negative"}
                for f, v in ranked
            ],
            "explanation": text,
        }

    def _local_text(self, ranked, pred_class: int, confidence: float, x) -> str:
        top = ranked[:3]
        parts = []
        for feat, val in top:
            actual = float(x[self.feature_names.index(feat)]) if hasattr(x, "__len__") else 0.0
            direction = "increases" if val > 0 else "decreases"
            parts.append(f"'{feat}' (value {actual:.3f}) {direction} the prediction by {abs(val):.3f}")
        label = "positive" if pred_class == 1 else "negative"
        return (
            f"Predicted {label} class with {confidence*100:.0f}% confidence. "
            + "Top contributors: " + "; ".join(parts) + "."
        )

    # ---------------------------------------------------------------- global
    def global_importance(self, X: np.ndarray, y: np.ndarray, nsamples: int = 300) -> dict:
        """Permutation importance with baseline accuracy."""
        rng = np.random.default_rng(self.seed)
        idx = rng.choice(len(X), size=min(nsamples, len(X)), replace=False)
        Xs, ys = X[idx], y[idx]
        baseline = float((self.predict_proba(Xs).argmax(axis=1) == ys).mean())

        importances = {}
        for i, name in enumerate(self.feature_names):
            Xp = Xs.copy()
            rng.shuffle(Xp[:, i])
            perm_acc = float((self.predict_proba(Xp).argmax(axis=1) == ys).mean())
            importances[name] = round(baseline - perm_acc, 4)

        ranked = sorted(importances.items(), key=lambda kv: kv[1], reverse=True)
        total = sum(v for _, v in importances.values()) or 1.0
        return {
            "baseline_accuracy": round(baseline, 4),
            "importances": [{"feature": k, "importance": v, "share": round(v / total, 4)} for k, v in ranked],
        }

    # ---------------------------------------------------------------- fairness
    def fairness_analysis(
        self,
        X: np.ndarray,
        y: np.ndarray,
        sensitive_idx: int = 0,
        sensitive_labels: Optional[List[str]] = None,
    ) -> dict:
        """Fairness metrics over a sensitive attribute column of X."""
        rng = np.random.default_rng(self.seed)
        Xs, ys = X, y
        groups = np.unique(Xs[:, sensitive_idx])
        labels = sensitive_labels or [f"group_{int(g)}" for g in groups]
        preds = self.predict_proba(Xs).argmax(axis=1)

        group_pred_rates, group_pos_rates, group_true_pos, group_sizes = [], [], [], []
        for g in groups:
            mask = Xs[:, sensitive_idx] == g
            if mask.sum() == 0:
                continue
            group_pred_rates.append(float(preds[mask].mean()))
            group_pos_rates.append(float(ys[mask].mean()))
            group_true_pos.append(float(((preds == 1) & (ys == 1))[mask].mean()))
            group_sizes.append(int(mask.sum()))

        demographic_parity = 1.0 - abs(group_pred_rates[0] - group_pred_rates[1]) if len(group_pred_rates) > 1 else 1.0
        equalized_odds = 1.0 - abs(group_true_pos[0] - group_true_pos[1]) if len(group_true_pos) > 1 else 1.0
        disparate_impact = (
            min(group_pred_rates) / max(group_pred_rates) if max(group_pred_rates) > 0 else 1.0
        )
        # statistical parity difference
        parity_diff = abs(group_pred_rates[0] - group_pred_rates[1]) if len(group_pred_rates) > 1 else 0.0

        if len(groups) == 2:
            bias = "low" if (demographic_parity >= 0.85 and equalized_odds >= 0.8) else "high"
        else:
            bias = "high" if (max(group_pred_rates) - min(group_pred_rates)) > 0.2 else "low"

        return {
            "groups": [
                {"label": labels[int(g)] if int(g) < len(labels) else f"group_{g}", "size": s,
                 "prediction_rate": round(r, 4), "positive_rate": round(p, 4),
                 "true_positive_rate": round(tp, 4)}
                for g, s, r, p, tp in zip(groups, group_sizes, group_pred_rates, group_pos_rates, group_true_pos)
            ],
            "demographic_parity": round(demographic_parity, 4),
            "equalized_odds": round(equalized_odds, 4),
            "disparate_impact": round(disparate_impact, 4),
            "statistical_parity_difference": round(parity_diff, 4),
            "bias_level": bias,
            "interpretation": (
                "No significant bias detected across groups." if bias == "low"
                else "Disparate prediction rates detected across groups — review feature "
                f"'{self.feature_names[sensitive_idx]}' and consider fairness mitigations."
            ),
        }

    def model_comparison(self, versions) -> dict:
        """Compare model versions across standard metrics."""
        rows = [
            {
                "version": v.get("version"),
                "accuracy": v.get("accuracy"),
                "precision": v.get("precision"),
                "recall": v.get("recall"),
                "f1": v.get("f1"),
                "status": v.get("status"),
            }
            for v in versions
        ]
        best = max(rows, key=lambda r: (r.get("f1") or 0), default=None)
        return {"versions": rows, "best_version": best}
