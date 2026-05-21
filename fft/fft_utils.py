"""
fft_utils.py - Shared utility functions for the FFT deepfake detection pipeline.

Covers: seeding, metrics (AUC, F1, Acc, EER), and CSV logging.
Metrics always operate on sigmoid probabilities, not raw logits.
"""

from __future__ import annotations

import csv
import random
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------

def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_eer(y_true: np.ndarray, scores: np.ndarray) -> float:
    """Equal Error Rate computed from the ROC curve."""
    from sklearn.metrics import roc_curve

    y_int = y_true.astype(np.int32)
    if len(np.unique(y_int)) < 2:
        return float("nan")
    fpr, tpr, _ = roc_curve(y_int, scores)
    fnr = 1.0 - tpr
    idx = np.nanargmin(np.abs(fpr - fnr))
    return float((fpr[idx] + fnr[idx]) / 2.0)


def compute_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Compute Accuracy, F1, ROC-AUC, and EER.
    probs: sigmoid probabilities (not raw logits).
    """
    from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

    y_hat = (probs >= threshold).astype(np.int32)
    y_int = y_true.astype(np.int32)

    out: Dict[str, float] = {}
    try:
        out["auc"] = float(roc_auc_score(y_int, probs))
    except ValueError:
        out["auc"] = float("nan")

    out["f1"] = float(f1_score(y_int, y_hat, zero_division=0))
    out["acc"] = float(accuracy_score(y_int, y_hat))
    out["eer"] = compute_eer(y_int.astype(np.float32), probs)
    return out


# ---------------------------------------------------------------------------
# CSV logging
# ---------------------------------------------------------------------------

def append_csv(rows: List[Dict], path: Path) -> None:
    """Append a list of dicts to a CSV file, writing header if needed."""
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow(r)
