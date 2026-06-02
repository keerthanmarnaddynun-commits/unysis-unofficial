"""
fusion_calibrate.py - Per-branch Platt scaling on logits (Option B: fit on val).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict

import numpy as np

from fusion_scores import prob_from_logit


@dataclass
class PlattCalibrator:
    """
    Platt scaling: P(y=1|x) = sigmoid(a * logit + b).
    Fit on raw branch logits and binary labels.
    """

    a: float = 1.0
    b: float = 0.0
    fitted: bool = False

    def fit(self, logits: np.ndarray, labels: np.ndarray) -> "PlattCalibrator":
        from sklearn.linear_model import LogisticRegression

        x = np.asarray(logits, dtype=np.float64).reshape(-1, 1)
        y = np.asarray(labels, dtype=np.int32).reshape(-1)
        if len(np.unique(y)) < 2:
            raise ValueError("Platt fit requires both classes in labels.")
        lr = LogisticRegression(
            penalty="l2",
            C=1.0,
            solver="lbfgs",
            max_iter=1000,
        )
        lr.fit(x, y)
        self.a = float(lr.coef_[0, 0])
        self.b = float(lr.intercept_[0])
        self.fitted = True
        return self

    def linear_term(self, logits: np.ndarray) -> np.ndarray:
        """Calibrated logit z = a * logit + b (before final sigmoid)."""
        return (self.a * np.asarray(logits, dtype=np.float64) + self.b).astype(np.float32)

    def predict_proba(self, logits: np.ndarray) -> np.ndarray:
        return prob_from_logit(self.linear_term(logits))

    def to_dict(self) -> Dict[str, Any]:
        return {"a": self.a, "b": self.b, "fitted": self.fitted}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PlattCalibrator":
        return cls(a=float(d["a"]), b=float(d["b"]), fitted=bool(d.get("fitted", True)))
