#!/usr/bin/env python3
"""
export_spatial_scores.py — Export validation logits/probs from trained spatial CNN.

Uses the same collect_paths + train_test_split (seed=42, val_split=0.2) as
train_deepfake_detection.py and fft fusion score export, so sample_id order
matches FFT val_scores.npz for fusion alignment.

Example:
  python export_spatial_scores.py \\
    --data_dir final_dataset_aligned \\
    --model_path training_output/best_model.pth
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional

import numpy as np
import torch
from sklearn.model_selection import train_test_split
from torch.amp import autocast
from tqdm import tqdm

# Repo root on path for train_deepfake_detection imports
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_FFT_DIR = _ROOT / "fft"
if str(_FFT_DIR) not in sys.path:
    sys.path.insert(0, str(_FFT_DIR))

from fusion_scores import path_to_sample_id, save_branch_scores
from train_deepfake_detection import (
    EfficientNetB4Binary,
    build_val_dataloader,
    collect_paths,
    set_seed,
)

# Must match train_deepfake_detection.py defaults and FFTConfig (seed=42, val_split=0.2)
DEFAULT_SEED = 42
DEFAULT_VAL_SPLIT = 0.2


@torch.no_grad()
def export_val_scores(
    data_dir: Path,
    model_path: Path,
    out_path: Path,
    *,
    seed: int = DEFAULT_SEED,
    val_split: float = DEFAULT_VAL_SPLIT,
    batch_size: int = 32,
    workers: int = 4,
    prefetch_factor: int = 2,
    device: Optional[torch.device] = None,
) -> None:
    set_seed(seed)
    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    data_dir = data_dir.resolve()
    model_path = model_path.resolve()
    out_path = out_path.resolve()

    if not model_path.is_file():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    paths, labels = collect_paths(data_dir)
    y_int = np.asarray(labels, dtype=np.int32)
    _, val_paths, _, val_labels = train_test_split(
        paths,
        labels,
        test_size=val_split,
        random_state=seed,
        stratify=y_int,
    )

    sample_ids = np.array(
        [path_to_sample_id(p, data_dir) for p in val_paths], dtype=object
    )

    val_loader = build_val_dataloader(
        val_paths,
        val_labels,
        batch_size=batch_size,
        workers=workers,
        prefetch_factor=prefetch_factor if workers > 0 else None,
    )

    ckpt = torch.load(model_path, map_location="cpu", weights_only=False)
    model = EfficientNetB4Binary(pretrained=False)
    state = ckpt.get("model_state_dict", ckpt)
    model.load_state_dict(state)
    model.to(device)
    model.eval()

    all_logits: List[float] = []
    all_labels: List[float] = []

    for x, y in tqdm(val_loader, desc="export spatial val scores"):
        x = x.to(device, non_blocking=True).float()
        with autocast(device_type="cuda", enabled=(device.type == "cuda")):
            logits = model(x).view(-1)
        all_logits.extend(logits.float().cpu().numpy().tolist())
        all_labels.extend(y.numpy().tolist())

    logits_arr = np.asarray(all_logits, dtype=np.float32)
    labels_arr = np.asarray(all_labels, dtype=np.float32)

    if len(logits_arr) != len(val_paths):
        raise RuntimeError(
            f"Exported {len(logits_arr)} scores but val split has {len(val_paths)} paths. "
            "Check dataloader / dataset length."
        )

    n_real = int(np.sum(labels_arr < 0.5))
    n_fake = int(len(labels_arr) - n_real)
    print(
        f"Val split: {len(val_paths)} images (real={n_real}, fake={n_fake}) | "
        f"seed={seed} val_split={val_split}"
    )
    print(f"Device: {device} | Model: {model_path}")

    save_branch_scores(out_path, sample_ids, logits_arr, labels_arr)
    print(f"Saved: {out_path}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export spatial CNN validation scores for fusion (Option B val split)."
    )
    p.add_argument("--data_dir", type=str, default="final_dataset_aligned")
    p.add_argument(
        "--model_path",
        type=str,
        default="training_output/best_model.pth",
    )
    p.add_argument(
        "--out_path",
        type=str,
        default=None,
        help="Output .npz (default: <model_dir>/val_scores.npz)",
    )
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--val_split", type=float, default=DEFAULT_VAL_SPLIT)
    p.add_argument("--batch_size", type=int, default=32)
    p.add_argument("--workers", type=int, default=4, help="DataLoader workers (Windows: 0-4)")
    p.add_argument("--prefetch_factor", type=int, default=2)
    p.add_argument("--device", type=str, default=None, help="cuda, cpu, or cuda:0")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    model_path = Path(args.model_path)
    out_path = (
        Path(args.out_path)
        if args.out_path
        else model_path.parent / "val_scores.npz"
    )
    device = torch.device(args.device) if args.device else None

    export_val_scores(
        data_dir=Path(args.data_dir),
        model_path=model_path,
        out_path=out_path,
        seed=args.seed,
        val_split=args.val_split,
        batch_size=args.batch_size,
        workers=args.workers,
        prefetch_factor=args.prefetch_factor,
        device=device,
    )


if __name__ == "__main__":
    main()
