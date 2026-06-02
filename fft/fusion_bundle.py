"""
fusion_bundle.py - Save/load fusion artifacts (Option B, val-fit).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from fusion_calibrate import PlattCalibrator
from fusion_methods import LogisticFusion, WeightedFusion
from fusion_scores import AlignmentReport
from fusion_threshold import ThresholdConfig

OPTION_B_NOTICE = (
    "split_protocol: option_b_val_only - Platt, fusion weights, and thresholds are fit on "
    "the same validation split used for base-model early stopping. Metrics may be "
    "slightly optimistic. For unbiased estimates, hold out a separate test set or use "
    "a dedicated fusion_cal split (Option A) in a future iteration."
)


def save_fusion_bundle(
    out_dir: str | Path,
    *,
    spatial_platt: PlattCalibrator,
    fft_platt: PlattCalibrator,
    weighted: WeightedFusion,
    logistic: LogisticFusion,
    selected_method: str,
    thresholds: ThresholdConfig,
    metrics_report: Dict[str, Any],
    alignment_report: AlignmentReport,
    extra_config: Optional[Dict[str, Any]] = None,
) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    config: Dict[str, Any] = {
        "version": "1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "split_protocol": "option_b_val_only",
        "notice": OPTION_B_NOTICE,
        "selected_fusion_method": selected_method,
        "feature_order": ["spatial_calibrated_z", "fft_calibrated_z"],
        **(extra_config or {}),
    }
    with (out_dir / "config.json").open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    with (out_dir / "spatial_platt.json").open("w", encoding="utf-8") as f:
        json.dump(spatial_platt.to_dict(), f, indent=2)
    with (out_dir / "fft_platt.json").open("w", encoding="utf-8") as f:
        json.dump(fft_platt.to_dict(), f, indent=2)
    with (out_dir / "weighted_fusion.json").open("w", encoding="utf-8") as f:
        json.dump(weighted.to_dict(), f, indent=2)
    with (out_dir / "logistic_fusion.json").open("w", encoding="utf-8") as f:
        json.dump(logistic.to_dict(), f, indent=2)
    with (out_dir / "thresholds.json").open("w", encoding="utf-8") as f:
        json.dump(thresholds.to_dict(), f, indent=2)
    with (out_dir / "metrics_report.json").open("w", encoding="utf-8") as f:
        json.dump(metrics_report, f, indent=2)
    with (out_dir / "alignment_report.json").open("w", encoding="utf-8") as f:
        json.dump(alignment_report.to_dict(), f, indent=2)

    print(f"Fusion bundle saved to {out_dir.resolve()}")
    return out_dir


@dataclass
class FusionBundle:
    config: Dict[str, Any]
    spatial_platt: PlattCalibrator
    fft_platt: PlattCalibrator
    weighted: WeightedFusion
    logistic: LogisticFusion
    selected_method: str
    thresholds: ThresholdConfig


def load_fusion_bundle(bundle_dir: str | Path) -> FusionBundle:
    bundle_dir = Path(bundle_dir)

    def _read(name: str) -> Dict[str, Any]:
        with (bundle_dir / name).open(encoding="utf-8") as f:
            return json.load(f)

    config = _read("config.json")
    return FusionBundle(
        config=config,
        spatial_platt=PlattCalibrator.from_dict(_read("spatial_platt.json")),
        fft_platt=PlattCalibrator.from_dict(_read("fft_platt.json")),
        weighted=WeightedFusion.from_dict(_read("weighted_fusion.json")),
        logistic=LogisticFusion.from_dict(_read("logistic_fusion.json")),
        selected_method=str(config.get("selected_fusion_method", "logistic")),
        thresholds=ThresholdConfig(**_read("thresholds.json")),
    )


def apply_fusion_bundle(
    bundle: FusionBundle,
    spatial_logits: np.ndarray,
    fft_logits: np.ndarray,
) -> np.ndarray:
    """Inference: raw branch logits -> fused probability."""
    z_s = bundle.spatial_platt.linear_term(spatial_logits)
    z_f = bundle.fft_platt.linear_term(fft_logits)
    if bundle.selected_method == "weighted":
        p_s = bundle.spatial_platt.predict_proba(spatial_logits)
        p_f = bundle.fft_platt.predict_proba(fft_logits)
        return bundle.weighted.fuse_probs(p_f, p_s)
    return bundle.logistic.fuse_linear(z_s, z_f)
