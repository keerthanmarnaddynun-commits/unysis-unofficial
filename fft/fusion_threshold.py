"""
fusion_threshold.py - Threshold tuning for F1 and EER on fused probabilities.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Tuple

import numpy as np

from fft_utils import compute_eer, compute_metrics


@dataclass
class ThresholdConfig:
    default: float = 0.5
    f1_threshold: float = 0.5
    f1_score: float = 0.0
    eer_threshold: float = 0.5
    eer_value: float = 0.0
    objective: str = "f1"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def find_threshold_max_f1(
    labels: np.ndarray,
    probs: np.ndarray,
    n_steps: int = 199,
) -> Tuple[float, float]:
    """Grid-search threshold in (0,1) maximizing F1."""
    from sklearn.metrics import f1_score

    y = labels.astype(np.int32).reshape(-1)
    p = probs.astype(np.float64).reshape(-1)
    if len(np.unique(y)) < 2:
        return 0.5, 0.0
    thresholds = np.linspace(0.01, 0.99, n_steps)
    best_t, best_f1 = 0.5, -1.0
    for t in thresholds:
        f1 = float(f1_score(y, (p >= t).astype(np.int32), zero_division=0))
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return best_t, best_f1


def find_threshold_eer(labels: np.ndarray, probs: np.ndarray) -> Tuple[float, float]:
    """Threshold at ROC point closest to equal error rate."""
    from sklearn.metrics import roc_curve

    y = labels.astype(np.int32).reshape(-1)
    p = probs.astype(np.float64).reshape(-1)
    if len(np.unique(y)) < 2:
        return 0.5, float("nan")
    fpr, tpr, thr = roc_curve(y, p)
    fnr = 1.0 - tpr
    idx = int(np.nanargmin(np.abs(fpr - fnr)))
    t = float(thr[idx]) if idx < len(thr) else 0.5
    eer = float((fpr[idx] + fnr[idx]) / 2.0)
    return t, eer


def tune_thresholds(
    labels: np.ndarray,
    fused_probs: np.ndarray,
    *,
    n_f1_steps: int = 199,
) -> ThresholdConfig:
    f1_t, f1_val = find_threshold_max_f1(labels, fused_probs, n_steps=n_f1_steps)
    eer_t, eer_val = find_threshold_eer(labels, fused_probs)
    return ThresholdConfig(
        default=f1_t,
        f1_threshold=f1_t,
        f1_score=f1_val,
        eer_threshold=eer_t,
        eer_value=eer_val,
        objective="f1",
    )


def metrics_at_thresholds(
    labels: np.ndarray,
    probs: np.ndarray,
    cfg: ThresholdConfig,
) -> Dict[str, Dict[str, float]]:
    out = {}
    out["@f1_threshold"] = compute_metrics(labels, probs, threshold=cfg.f1_threshold)
    out["@eer_threshold"] = compute_metrics(labels, probs, threshold=cfg.eer_threshold)
    out["@default"] = compute_metrics(labels, probs, threshold=cfg.default)
    return out
