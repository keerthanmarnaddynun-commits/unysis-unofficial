"""
fusion_eval.py - Late-fusion evaluation (Option B: val-split fit, no CNN retrain).

Option B notice:
  Platt calibration, fusion weights, logistic stacking, and thresholds are all fit on
  the same validation scores used for base-model early stopping. Reported metrics may
  be slightly optimistic. Do not treat them as unbiased test performance.

Usage (FFT-only metrics):
  python fusion_eval.py --fft_scores fft_output/val_scores.npz

Usage (full fusion pipeline + save bundle):
  python fusion_eval.py \\
    --fft_scores fft_output/val_scores.npz \\
    --spatial_scores training_output/val_scores.npz \\
    --out_dir fusion_bundle

Generate FFT val scores (with sample_id + logits + probs):
  python fusion_eval.py --generate_fft_scores --data_dir final_dataset_aligned \\
    --fft_model_path fft_output/best_fft_model.pth

Scores file format (.npz):
  sample_id : str array, relative path e.g. real/face.jpg
  logits    : float32 (N,)
  probs     : float32 (N,)  - sigmoid(logits)
  labels    : float32 (N,)  - 0=real, 1=fake

Legacy .npz (probs + labels only) still loads; re-export with --generate_fft_scores
for sample_id alignment.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import numpy as np

# Ensure fft/ is on path when run as script from repo root or fft/
_FFT_DIR = Path(__file__).resolve().parent
if str(_FFT_DIR) not in sys.path:
    sys.path.insert(0, str(_FFT_DIR))

from fft_utils import compute_metrics
from fusion_bundle import OPTION_B_NOTICE, apply_fusion_bundle, load_fusion_bundle
from fusion_pipeline import print_metrics, run_fusion_pipeline
from fusion_scores import (
    load_branch_scores,
    load_scores,
    path_to_sample_id,
    save_branch_scores,
    save_scores,
)
from fusion_methods import search_best_fusion_weight, weighted_late_fusion


# Re-export for backward compatibility
__all__ = [
    "load_scores",
    "save_scores",
    "weighted_late_fusion",
    "search_best_fusion_weight",
    "generate_fft_scores",
]


def generate_fft_scores(
    data_dir: str,
    model_path: str,
    out_path: str,
    cfg_overrides: Optional[dict] = None,
) -> None:
    """Run FFT model on val split; save sample_id, logits, probs, labels."""
    import torch
    from sklearn.model_selection import train_test_split
    from tqdm import tqdm

    from fft_config import FFTConfig
    from fft_dataset import collect_paths, build_val_loader
    from fft_model import build_model
    from fft_preprocess import build_radial_emphasis_mask

    cfg = FFTConfig(**(cfg_overrides or {}))
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    data_root = Path(data_dir).resolve()

    paths, labels = collect_paths(data_root)
    y_int = np.array(labels, dtype=np.int32)
    _, val_paths, _, val_labels = train_test_split(
        paths,
        labels,
        test_size=cfg.val_split,
        random_state=cfg.seed,
        stratify=y_int,
    )

    sample_ids = np.array(
        [path_to_sample_id(p, data_root) for p in val_paths], dtype=object
    )

    radial_mask = None
    if cfg.radial_emphasis:
        radial_mask = build_radial_emphasis_mask(
            cfg.image_size, cfg.radial_emphasis_sigma
        )

    dataset_mean, dataset_std = None, None
    if cfg.norm_mode == "dataset":
        from fft_preprocess import load_stats

        dataset_mean, dataset_std = load_stats(cfg.stats_file)

    val_loader = build_val_loader(
        val_paths, val_labels, cfg, dataset_mean, dataset_std, radial_mask
    )

    ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
    arch = ckpt.get("arch", "resnet18")
    model = build_model(arch).to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()

    all_logits, all_labels = [], []
    with torch.no_grad():
        for x, y in tqdm(val_loader, desc="generating FFT scores"):
            x = x.to(device)
            logits = model(x).view(-1).cpu().numpy()
            all_logits.extend(logits.tolist())
            all_labels.extend(y.numpy().tolist())

    logits_arr = np.array(all_logits, dtype=np.float32)
    labels_arr = np.array(all_labels, dtype=np.float32)
    if len(logits_arr) != len(sample_ids):
        raise RuntimeError(
            f"Score count {len(logits_arr)} != val_paths {len(sample_ids)}; "
            "check dataloader order."
        )

    save_branch_scores(
        out_path,
        sample_ids,
        logits_arr,
        labels_arr,
    )


def _eval_fft_only(fft_scores: str, threshold: float) -> None:
    fft = load_branch_scores(fft_scores)
    m = compute_metrics(fft.labels, fft.probs, threshold=threshold)
    print(f"FFT scores loaded: {len(fft.probs)} samples")
    print_metrics("FFT-only", m)


def _legacy_quick_fusion(
    fft_probs: np.ndarray,
    spatial_probs: np.ndarray,
    labels: np.ndarray,
    threshold: float,
    n_steps: int,
) -> None:
    """Uncalibrated weighted search (--no_fit_fusion)."""
    spatial_m = compute_metrics(labels, spatial_probs, threshold=threshold)
    print_metrics("Spatial-only (uncalibrated)", spatial_m)
    best_w, best_m = search_best_fusion_weight(
        fft_probs, spatial_probs, labels, n_steps=n_steps
    )
    print(f"\nBest uncalibrated fusion weight w_spatial={best_w:.2f} (Option B: not saved)")
    print_metrics(f"Fused uncalibrated (w={best_w:.2f})", best_m)
    fused = weighted_late_fusion(fft_probs, spatial_probs, w_spatial=best_w)
    print_metrics("Fused @fixed threshold", compute_metrics(labels, fused, threshold=threshold))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="FFT + Spatial fusion (Option B: val-fit, modular pipeline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=OPTION_B_NOTICE,
    )
    p.add_argument("--fft_scores", type=str, default=None, help="FFT branch .npz")
    p.add_argument(
        "--spatial_scores",
        type=str,
        default=None,
        help="Spatial branch .npz (required for fusion)",
    )
    p.add_argument(
        "--out_dir",
        type=str,
        default="fusion_bundle",
        help="Directory for fusion artifacts (with --fit_fusion)",
    )
    p.add_argument(
        "--no_fit_fusion",
        action="store_true",
        help="Legacy mode: uncalibrated weighted search only (no bundle saved)",
    )
    p.add_argument("--threshold", type=float, default=0.5, help="Fixed threshold for quick metrics")
    p.add_argument("--n_fusion_steps", type=int, default=21)
    p.add_argument("--n_threshold_steps", type=int, default=199)
    p.add_argument(
        "--bundle_dir",
        type=str,
        default=None,
        help="Load saved bundle and verify fused probs match recomputation (optional)",
    )
    # FFT score generation
    p.add_argument("--generate_fft_scores", action="store_true")
    p.add_argument("--data_dir", type=str, default="final_dataset_aligned")
    p.add_argument("--fft_model_path", type=str, default="fft_output/best_fft_model.pth")
    p.add_argument("--fft_scores_out", type=str, default="fft_output/val_scores.npz")
    return p.parse_args()


def main() -> None:
    args = parse_args()

    if args.generate_fft_scores:
        generate_fft_scores(
            data_dir=args.data_dir,
            model_path=args.fft_model_path,
            out_path=args.fft_scores_out,
        )
        if args.fft_scores is None:
            args.fft_scores = args.fft_scores_out

    if args.fft_scores is None:
        print("No --fft_scores provided. Nothing to evaluate.")
        return

    if args.spatial_scores is None:
        _eval_fft_only(args.fft_scores, args.threshold)
        return

    fft = load_branch_scores(args.fft_scores)
    spatial = load_branch_scores(args.spatial_scores)

    if not args.no_fit_fusion:
        run_fusion_pipeline(
            fft,
            spatial,
            out_dir=Path(args.out_dir),
            n_fusion_steps=args.n_fusion_steps,
            n_threshold_steps=args.n_threshold_steps,
            fft_scores_path=args.fft_scores,
            spatial_scores_path=args.spatial_scores,
        )
    else:
        print("\n=== Quick uncalibrated fusion (--no_fit_fusion) ===")
        print(OPTION_B_NOTICE)
        from fusion_scores import align_branches

        aligned, report = align_branches(fft, spatial)
        print(f"Aligned {report.n_joined} samples")
        _legacy_quick_fusion(
            aligned.fft_probs,
            aligned.spatial_probs,
            aligned.labels,
            args.threshold,
            args.n_fusion_steps,
        )

    if args.bundle_dir:
        bundle = load_fusion_bundle(args.bundle_dir)
        aligned, _ = __import__("fusion_scores").align_branches(fft, spatial)
        p = apply_fusion_bundle(
            bundle, aligned.spatial_logits, aligned.fft_logits
        )
        print_metrics(
            f"Bundle verify ({bundle.selected_method})",
            compute_metrics(aligned.labels, p, threshold=bundle.thresholds.default),
        )


if __name__ == "__main__":
    main()
