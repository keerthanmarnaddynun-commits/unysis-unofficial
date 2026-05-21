"""
fusion_pipeline.py - Option B fusion fit/eval on validation scores (no CNN retrain).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from fft_utils import compute_metrics
from fusion_bundle import OPTION_B_NOTICE, save_fusion_bundle
from fusion_calibrate import PlattCalibrator
from fusion_methods import LogisticFusion, WeightedFusion, search_best_fusion_weight
from fusion_scores import (
    AlignedScores,
    AlignmentReport,
    BranchScores,
    align_branches,
    sanity_check_scores,
    save_alignment_report,
)
from fusion_threshold import ThresholdConfig, metrics_at_thresholds, tune_thresholds


def print_metrics(label: str, m: Dict[str, float]) -> None:
    print(
        f"[{label}] AUC={m.get('auc', float('nan')):.4f} "
        f"F1={m.get('f1', float('nan')):.4f} "
        f"Acc={m.get('acc', float('nan')):.4f} "
        f"EER={m.get('eer', float('nan')):.4f}"
    )


def run_fusion_pipeline(
    fft: BranchScores,
    spatial: BranchScores,
    *,
    out_dir: Path,
    n_fusion_steps: int = 21,
    n_threshold_steps: int = 199,
    fft_scores_path: Optional[str] = None,
    spatial_scores_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Fit Platt (per branch), fusion models, thresholds on val; save bundle + metrics.
    """
    print("\n=== Option B fusion (validation split) ===")
    print(OPTION_B_NOTICE)
    print()

    for name, branch in [("FFT", fft), ("Spatial", spatial)]:
        for msg in sanity_check_scores(branch, name):
            print(f"SANITY WARNING [{name}]: {msg}")

    aligned, report = align_branches(fft, spatial)
    print(
        f"Aligned {report.n_joined} samples "
        f"(fft={report.n_fft}, spatial={report.n_spatial}, "
        f"fft_only={report.n_fft_only}, spatial_only={report.n_spatial_only})"
    )
    for w in report.warnings:
        print(f"  align: {w}")

    y = aligned.labels
    metrics_report: Dict[str, Any] = {
        "split_protocol": "option_b_val_only",
        "notice": OPTION_B_NOTICE,
        "n_samples": int(len(y)),
        "branches": {},
        "fusion": {},
        "thresholds": {},
    }

    # ---- Branch baselines (uncalibrated) ----
    m_fft = compute_metrics(y, aligned.fft_probs)
    m_sp = compute_metrics(y, aligned.spatial_probs)
    metrics_report["branches"]["fft_uncalibrated"] = m_fft
    metrics_report["branches"]["spatial_uncalibrated"] = m_sp
    print_metrics("FFT-only (uncalibrated)", m_fft)
    print_metrics("Spatial-only (uncalibrated)", m_sp)

    # ---- Platt per branch ----
    fft_platt = PlattCalibrator().fit(aligned.fft_logits, y)
    spatial_platt = PlattCalibrator().fit(aligned.spatial_logits, y)
    p_fft_cal = fft_platt.predict_proba(aligned.fft_logits)
    p_sp_cal = spatial_platt.predict_proba(aligned.spatial_logits)
    z_fft = fft_platt.linear_term(aligned.fft_logits)
    z_sp = spatial_platt.linear_term(aligned.spatial_logits)

    m_fft_c = compute_metrics(y, p_fft_cal)
    m_sp_c = compute_metrics(y, p_sp_cal)
    metrics_report["branches"]["fft_calibrated"] = m_fft_c
    metrics_report["branches"]["spatial_calibrated"] = m_sp_c
    print_metrics("FFT (Platt-calibrated)", m_fft_c)
    print_metrics("Spatial (Platt-calibrated)", m_sp_c)

    # ---- Weighted fusion on calibrated probs ----
    best_w, m_w = search_best_fusion_weight(
        p_fft_cal, p_sp_cal, y, n_steps=n_fusion_steps
    )
    weighted = WeightedFusion(w_spatial=best_w)
    p_weighted = weighted.fuse_probs(p_fft_cal, p_sp_cal)
    print(f"\nBest calibrated weighted fusion w_spatial={best_w:.3f}")
    print_metrics("Fused weighted (calibrated)", m_w)
    metrics_report["fusion"]["weighted"] = {
        "w_spatial": best_w,
        "selection_auc": m_w.get("auc"),
        "metrics": m_w,
    }

    # ---- Logistic stacking on calibrated linear terms ----
    logistic = LogisticFusion().fit(z_sp, z_fft, y)
    p_logistic = logistic.fuse_linear(z_sp, z_fft)
    m_log = compute_metrics(y, p_logistic)
    print_metrics("Fused logistic (calibrated z)", m_log)
    metrics_report["fusion"]["logistic"] = {
        "coef_spatial": logistic.coef_spatial,
        "coef_fft": logistic.coef_fft,
        "intercept": logistic.intercept,
        "selection_auc": m_log.get("auc"),
        "metrics": m_log,
    }

    # ---- Select fusion method by AUC ----
    auc_w = m_w.get("auc", float("nan"))
    auc_l = m_log.get("auc", float("nan"))
    if np.isnan(auc_l) or (not np.isnan(auc_w) and auc_w >= auc_l):
        selected = "weighted"
        p_fused = p_weighted
        sel_auc = auc_w
    else:
        selected = "logistic"
        p_fused = p_logistic
        sel_auc = auc_l
    print(f"\nSelected fusion method: {selected} (AUC={sel_auc:.4f})")

    m_fused = compute_metrics(y, p_fused)
    print_metrics(f"Final fused ({selected})", m_fused)
    metrics_report["fusion"]["selected"] = selected
    metrics_report["fusion"]["selected_metrics"] = m_fused

    # ---- Thresholds ----
    thr_cfg = tune_thresholds(y, p_fused, n_f1_steps=n_threshold_steps)
    thr_metrics = metrics_at_thresholds(y, p_fused, thr_cfg)
    metrics_report["thresholds"] = {
        "config": thr_cfg.to_dict(),
        "metrics_at_thresholds": thr_metrics,
    }
    print(
        f"\nThresholds: F1-opt t={thr_cfg.f1_threshold:.4f} (F1={thr_cfg.f1_score:.4f}) | "
        f"EER t={thr_cfg.eer_threshold:.4f} (EER={thr_cfg.eer_value:.4f}) | "
        f"default={thr_cfg.default:.4f}"
    )
    print_metrics("@F1 threshold", thr_metrics["@f1_threshold"])
    print_metrics("@EER threshold", thr_metrics["@eer_threshold"])

    extra = {}
    if fft_scores_path:
        extra["fft_scores_path"] = str(fft_scores_path)
    if spatial_scores_path:
        extra["spatial_scores_path"] = str(spatial_scores_path)

    save_fusion_bundle(
        out_dir,
        spatial_platt=spatial_platt,
        fft_platt=fft_platt,
        weighted=weighted,
        logistic=logistic,
        selected_method=selected,
        thresholds=thr_cfg,
        metrics_report=metrics_report,
        alignment_report=report,
        extra_config=extra,
    )
    save_alignment_report(report, out_dir / "alignment_report.json")

    return metrics_report
