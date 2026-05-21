"""
fusion_methods.py - Calibrated weighted average and logistic stacking fusion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple

import numpy as np

from fft_utils import compute_metrics
from fusion_scores import prob_from_logit


@dataclass
class WeightedFusion:
    w_spatial: float = 0.5

    def fuse_probs(self, fft_probs: np.ndarray, spatial_probs: np.ndarray) -> np.ndarray:
        w = self.w_spatial
        return (w * spatial_probs + (1.0 - w) * fft_probs).astype(np.float32)

    def to_dict(self) -> Dict[str, Any]:
        return {"method": "weighted", "w_spatial": self.w_spatial}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WeightedFusion":
        return cls(w_spatial=float(d["w_spatial"]))


@dataclass
class LogisticFusion:
    """Fuse calibrated linear terms z_spatial, z_fft: p = sigmoid(b0 + b1*z_s + b2*z_f)."""

    intercept: float = 0.0
    coef_spatial: float = 1.0
    coef_fft: float = 1.0
    fitted: bool = False

    def fit(self, z_spatial: np.ndarray, z_fft: np.ndarray, labels: np.ndarray) -> "LogisticFusion":
        from sklearn.linear_model import LogisticRegression

        x = np.column_stack(
            [
                np.asarray(z_spatial, dtype=np.float64),
                np.asarray(z_fft, dtype=np.float64),
            ]
        )
        y = np.asarray(labels, dtype=np.int32).reshape(-1)
        if len(np.unique(y)) < 2:
            raise ValueError("Logistic fusion requires both classes.")
        lr = LogisticRegression(
            penalty="l2",
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
            max_iter=2000,
        )
        lr.fit(x, y)
        self.intercept = float(lr.intercept_[0])
        self.coef_spatial = float(lr.coef_[0, 0])
        self.coef_fft = float(lr.coef_[0, 1])
        self.fitted = True
        return self

    def fuse_linear(self, z_spatial: np.ndarray, z_fft: np.ndarray) -> np.ndarray:
        z = (
            self.intercept
            + self.coef_spatial * np.asarray(z_spatial, dtype=np.float64)
            + self.coef_fft * np.asarray(z_fft, dtype=np.float64)
        )
        return prob_from_logit(z.astype(np.float32))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "method": "logistic",
            "intercept": self.intercept,
            "coef_spatial": self.coef_spatial,
            "coef_fft": self.coef_fft,
            "fitted": self.fitted,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LogisticFusion":
        return cls(
            intercept=float(d["intercept"]),
            coef_spatial=float(d["coef_spatial"]),
            coef_fft=float(d["coef_fft"]),
            fitted=bool(d.get("fitted", True)),
        )


def weighted_late_fusion(
    fft_probs: np.ndarray,
    spatial_probs: np.ndarray,
    w_spatial: float,
) -> np.ndarray:
    return (w_spatial * spatial_probs + (1.0 - w_spatial) * fft_probs).astype(np.float32)


def search_best_fusion_weight(
    fft_probs: np.ndarray,
    spatial_probs: np.ndarray,
    labels: np.ndarray,
    n_steps: int = 21,
) -> Tuple[float, Dict[str, float]]:
    best_w = 0.0
    best_auc = -1.0
    best_metrics: Dict[str, float] = {}
    for w in np.linspace(0.0, 1.0, n_steps):
        fused = weighted_late_fusion(fft_probs, spatial_probs, w_spatial=float(w))
        m = compute_metrics(labels, fused)
        if not np.isnan(m["auc"]) and m["auc"] > best_auc:
            best_auc = m["auc"]
            best_w = float(w)
            best_metrics = m
    return best_w, best_metrics
