#!/usr/bin/env python3
"""
Compare CNN fake scores: GAN fakes (final_dataset_aligned) vs TPDNE (test_images/fake).

Uses model loading and preprocessing from test_cnn.py (no training code changes).

Example (Windows; avoid D:\\python_packages shadowing numpy)::

    $env:PYTHONNOUSERSITE='1'
    cd D:\\forsen
    D:\\envs\\gpu_env\\python.exe compare_gan_sources.py --face_crop --skip_no_face

Aligned GAN fakes are 380x380 crops; TPDNE images need the same pipeline — use
identical flags for both groups (e.g. --face_crop for both, or neither).
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import torch
from tqdm import tqdm

from test_cnn import (
    DEFAULT_ALIGNED_DIR,
    DEFAULT_MODEL_PATH,
    SUPPORTED_EXTS,
    get_transform,
    infer_one,
    iter_image_paths,
    load_image_pil,
    load_model,
)

DEFAULT_GAN_FAKE_DIR = DEFAULT_ALIGNED_DIR / "fake"
DEFAULT_TPDNE_DIR = Path("test_images") / "fake"
DEFAULT_OUT_CSV = Path("gan_source_comparison.csv")
DEFAULT_SAMPLE_N = 50
DEFAULT_SEED = 42


@dataclass
class GroupSpec:
    key: str
    label: str
    directory: Path
    path_filter: Optional[str] = "gan_fake"  # filename prefix; None = all images


@dataclass
class GroupStats:
    group: str
    label: str
    n_requested: int
    n_evaluated: int
    n_skipped: int
    mean_fake_prob: float
    min_fake_prob: float
    max_fake_prob: float
    std_fake_prob: float
    n_pred_fake: int
    accuracy: float
    threshold: float


def collect_gan_fake_paths(root: Path, prefix: str = "gan_fake") -> List[Path]:
    """GAN-like aligned fakes (gan_fake_*.jpg)."""
    out: List[Path] = []
    for p in root.rglob("*"):
        if p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if p.name.lower().startswith(prefix.lower()):
            out.append(p)
    return sorted(out)


def collect_all_paths(root: Path) -> List[Path]:
    return iter_image_paths(root)


def sample_paths(paths: Sequence[Path], n: int, seed: int) -> List[Path]:
    rng = random.Random(seed)
    paths = list(paths)
    if len(paths) <= n:
        return paths
    return rng.sample(paths, n)


def run_group(
    spec: GroupSpec,
    paths: List[Path],
    model,
    device: torch.device,
    transform,
    *,
    face_crop: bool,
    skip_no_face: bool,
    resize_if_not_380: bool,
    invert_output: bool,
    threshold: float,
) -> tuple[List[Dict], List[Dict]]:
    """Returns (per_image_rows, skipped_rows)."""
    per_image: List[Dict] = []
    skipped: List[Dict] = []

    for p in tqdm(paths, desc=spec.key, leave=False):
        try:
            pil = load_image_pil(p)
            result = infer_one(
                p,
                pil,
                model,
                device,
                transform,
                face_crop=face_crop,
                skip_no_face=skip_no_face,
                resize_if_not_380=resize_if_not_380,
                invert_output=invert_output,
                threshold=threshold,
            )
            if result is None:
                skipped.append(
                    {
                        "row_type": "image",
                        "group": spec.key,
                        "path": str(p),
                        "status": "skipped_no_face",
                    }
                )
                continue
            per_image.append(
                {
                    "row_type": "image",
                    "group": spec.key,
                    "group_label": spec.label,
                    "path": str(p),
                    "filename": p.name,
                    "logit": f"{result.logit:.6f}",
                    "prob_fake": f"{result.prob_fake:.6f}",
                    "pred_fake": result.pred_fake,
                    "pred_label": result.pred_label,
                    "face_detected": result.face_detected,
                    "status": "ok",
                }
            )
        except Exception as exc:
            skipped.append(
                {
                    "row_type": "image",
                    "group": spec.key,
                    "path": str(p),
                    "status": f"error:{exc}",
                }
            )
    return per_image, skipped


def summarize_group(
    spec: GroupSpec,
    per_image: List[Dict],
    n_requested: int,
    n_skipped: int,
    threshold: float,
) -> GroupStats:
    probs = [float(r["prob_fake"]) for r in per_image if r.get("status") == "ok"]
    preds = [int(r["pred_fake"]) for r in per_image if r.get("status") == "ok"]
    n = len(probs)
    if n == 0:
        return GroupStats(
            group=spec.key,
            label=spec.label,
            n_requested=n_requested,
            n_evaluated=0,
            n_skipped=n_skipped,
            mean_fake_prob=float("nan"),
            min_fake_prob=float("nan"),
            max_fake_prob=float("nan"),
            std_fake_prob=float("nan"),
            n_pred_fake=0,
            accuracy=float("nan"),
            threshold=threshold,
        )
    arr = np.asarray(probs, dtype=np.float64)
    pred_arr = np.asarray(preds, dtype=np.int32)
    return GroupStats(
        group=spec.key,
        label=spec.label,
        n_requested=n_requested,
        n_evaluated=n,
        n_skipped=n_skipped,
        mean_fake_prob=float(np.mean(arr)),
        min_fake_prob=float(np.min(arr)),
        max_fake_prob=float(np.max(arr)),
        std_fake_prob=float(np.std(arr)),
        n_pred_fake=int(np.sum(pred_arr == 1)),
        accuracy=float(np.mean(pred_arr == 1)),  # ground truth: all fake
        threshold=threshold,
    )


def print_group_stats(stats: GroupStats) -> None:
    print(f"\n{'=' * 72}")
    print(f"GROUP: {stats.label} ({stats.group})")
    print(f"{'=' * 72}")
    print(f"  Sampled: {stats.n_requested}  |  Evaluated: {stats.n_evaluated}  |  Skipped: {stats.n_skipped}")
    print(
        f"  fake_prob: mean={stats.mean_fake_prob:.4f}  min={stats.min_fake_prob:.4f}  "
        f"max={stats.max_fake_prob:.4f}  std={stats.std_fake_prob:.4f}"
    )
    print(f"  Predicted fake (prob >= {stats.threshold}): {stats.n_pred_fake} / {stats.n_evaluated}")
    print(f"  Accuracy (GT=fake for all): {stats.accuracy:.4f}")


def write_csv(
    out_path: Path,
    summaries: List[GroupStats],
    per_image_rows: List[Dict],
    preprocess_meta: Dict[str, str],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "row_type",
        "group",
        "group_label",
        "n_requested",
        "n_evaluated",
        "n_skipped",
        "mean_fake_prob",
        "min_fake_prob",
        "max_fake_prob",
        "std_fake_prob",
        "n_pred_fake",
        "accuracy_all_fake_gt",
        "threshold",
        "face_crop",
        "skip_no_face",
        "resize_if_not_380",
        "model_path",
        "path",
        "filename",
        "logit",
        "prob_fake",
        "pred_fake",
        "pred_label",
        "face_detected",
        "status",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for s in summaries:
            writer.writerow(
                {
                    "row_type": "summary",
                    "group": s.group,
                    "group_label": s.label,
                    "n_requested": s.n_requested,
                    "n_evaluated": s.n_evaluated,
                    "n_skipped": s.n_skipped,
                    "mean_fake_prob": f"{s.mean_fake_prob:.6f}",
                    "min_fake_prob": f"{s.min_fake_prob:.6f}",
                    "max_fake_prob": f"{s.max_fake_prob:.6f}",
                    "std_fake_prob": f"{s.std_fake_prob:.6f}",
                    "n_pred_fake": s.n_pred_fake,
                    "accuracy_all_fake_gt": f"{s.accuracy:.6f}",
                    "threshold": s.threshold,
                    **preprocess_meta,
                }
            )
        for row in per_image_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Compare CNN scores: aligned GAN fakes vs test_images/fake (TPDNE)."
    )
    p.add_argument("--gan_dir", type=str, default=str(DEFAULT_GAN_FAKE_DIR))
    p.add_argument("--tpdne_dir", type=str, default=str(DEFAULT_TPDNE_DIR))
    p.add_argument("--gan_prefix", type=str, default="gan_fake", help="Filename prefix for GAN fakes")
    p.add_argument("--model_path", type=str, default=str(DEFAULT_MODEL_PATH))
    p.add_argument("--out_csv", type=str, default=str(DEFAULT_OUT_CSV))
    p.add_argument("--n_sample", type=int, default=DEFAULT_SAMPLE_N)
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--threshold", type=float, default=None, help="Override checkpoint threshold")
    p.add_argument("--face_crop", action="store_true", help="MTCNN align both groups (recommended for TPDNE)")
    p.add_argument("--skip_no_face", action="store_true", help="Skip images with no face when face_crop")
    p.add_argument(
        "--resize_if_not_380",
        action="store_true",
        default=True,
        help="Resize non-380 inputs when not using face_crop (default: on)",
    )
    p.add_argument("--no_resize_if_not_380", action="store_false", dest="resize_if_not_380")
    p.add_argument("--invert_output", action="store_true")
    p.add_argument("--device", type=str, default=None)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model_path = Path(args.model_path).resolve()
    out_csv = Path(args.out_csv).resolve()

    model, meta = load_model(model_path, device)
    threshold = float(args.threshold if args.threshold is not None else meta.get("threshold", 0.5))
    transform = get_transform()

    preprocess_meta = {
        "face_crop": str(args.face_crop),
        "skip_no_face": str(args.skip_no_face),
        "resize_if_not_380": str(args.resize_if_not_380),
        "model_path": str(model_path),
    }

    specs = [
        GroupSpec(
            key="aligned_gan_fake",
            label="GAN-like fakes (final_dataset_aligned/fake, gan_fake_*)",
            directory=Path(args.gan_dir).resolve(),
            path_filter=args.gan_prefix,
        ),
        GroupSpec(
            key="tpdne_test_fake",
            label="ThisPersonDoesNotExist (test_images/fake)",
            directory=Path(args.tpdne_dir).resolve(),
            path_filter=None,
        ),
    ]

    print("GAN source comparison")
    print(f"  Device: {device}  Model: {model_path}  Threshold: {threshold}")
    print(
        f"  Preprocess: face_crop={args.face_crop} skip_no_face={args.skip_no_face} "
        f"resize_if_not_380={args.resize_if_not_380}"
    )

    all_per_image: List[Dict] = []
    summaries: List[GroupStats] = []

    for spec in specs:
        if not spec.directory.is_dir():
            print(f"[!] Missing directory: {spec.directory}", file=sys.stderr)
            return 1
        if spec.path_filter:
            pool = collect_gan_fake_paths(spec.directory, prefix=spec.path_filter)
        else:
            pool = collect_all_paths(spec.directory)
        subseed = args.seed + (0 if spec.key == "aligned_gan_fake" else 1)
        sampled = sample_paths(pool, args.n_sample, subseed)
        print(f"\n{spec.label}: {len(pool)} available, evaluating {len(sampled)} (requested {args.n_sample})")

        per_image, skipped = run_group(
            spec,
            sampled,
            model,
            device,
            transform,
            face_crop=args.face_crop,
            skip_no_face=args.skip_no_face,
            resize_if_not_380=args.resize_if_not_380,
            invert_output=args.invert_output,
            threshold=threshold,
        )
        all_per_image.extend(per_image)
        all_per_image.extend(skipped)
        stats = summarize_group(spec, per_image, len(sampled), len(skipped), threshold)
        summaries.append(stats)
        print_group_stats(stats)

    write_csv(out_csv, summaries, all_per_image, preprocess_meta)
    print(f"\nSaved: {out_csv}")

    if len(summaries) == 2:
        g, t = summaries
        print("\n--- Comparison ---")
        print(f"  Mean P(fake):  GAN={g.mean_fake_prob:.4f}  TPDNE={t.mean_fake_prob:.4f}  "
              f"delta={g.mean_fake_prob - t.mean_fake_prob:+.4f}")
        print(f"  Accuracy:      GAN={g.accuracy:.4f}  TPDNE={t.accuracy:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
