"""
train_fft.py - Standalone training script for the FFT deepfake detection branch.

Features:
  - Stratified train/val split
  - AMP mixed precision (CUDA)
  - Early stopping on validation AUC
  - Resume support (model, optimizer, scaler, epoch, phase)
  - Per-epoch checkpoint: latest_fft_checkpoint.pth
  - Best model checkpoint: best_fft_model.pth
  - CSV training logs
  - Windows-compatible (all dataloader/multiprocessing code inside __main__)

Usage:
  python train_fft.py --data_dir final_dataset_aligned --device cuda:0
  python train_fft.py --resume fft_output/latest_fft_checkpoint.pth
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from sklearn.model_selection import train_test_split
from torch.amp import GradScaler, autocast
from tqdm import tqdm

from fft_config import FFTConfig
from fft_dataset import (
    build_or_load_stats,
    build_train_loader,
    build_val_loader,
    collect_paths,
)
from fft_model import build_loss, build_model
from fft_preprocess import build_radial_emphasis_mask
from fft_utils import append_csv, compute_metrics, set_seed


# ---------------------------------------------------------------------------
# Training helpers
# ---------------------------------------------------------------------------

def train_one_epoch(
    model: nn.Module,
    loader,
    criterion: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: GradScaler,
    device: torch.device,
    amp: bool,
) -> float:
    model.train()
    total_loss = 0.0
    n = 0
    for x, y in tqdm(loader, desc="train", leave=False):
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)
        with autocast(device_type="cuda", enabled=(amp and device.type == "cuda")):
            logits = model(x)
            loss = criterion(logits.view(-1), y)

        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()

        total_loss += float(loss.detach().cpu())
        n += 1

    return total_loss / max(n, 1)


@torch.no_grad()
def validate(
    model: nn.Module,
    loader,
    device: torch.device,
    amp: bool,
    threshold: float = 0.5,
) -> Dict[str, float]:
    model.eval()
    all_probs: List[float] = []
    all_true: List[float] = []

    for x, y in tqdm(loader, desc="val", leave=False):
        x = x.to(device, non_blocking=True)
        with autocast(device_type="cuda", enabled=(amp and device.type == "cuda")):
            logits = model(x)
        probs = torch.sigmoid(logits).view(-1).cpu().numpy()
        all_probs.extend(probs.tolist())
        all_true.extend(y.numpy().tolist())

    return compute_metrics(
        np.array(all_true, dtype=np.float32),
        np.array(all_probs, dtype=np.float32),
        threshold=threshold,
    )


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def save_checkpoint(
    path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: GradScaler,
    epoch: int,
    best_auc: float,
) -> None:
    torch.save(
        {
            "epoch": epoch,
            "model_state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
            "optimizer_state_dict": optimizer.state_dict(),
            "scaler_state_dict": scaler.state_dict(),
            "best_auc": best_auc,
        },
        path,
    )


def load_checkpoint(
    path: str | Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scaler: GradScaler,
    device: torch.device,
) -> Tuple[int, float]:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    model.load_state_dict(ckpt["model_state_dict"])
    optimizer.load_state_dict(ckpt["optimizer_state_dict"])
    scaler.load_state_dict(ckpt["scaler_state_dict"])
    model.to(device)
    start_epoch = ckpt.get("epoch", -1) + 1
    best_auc = ckpt.get("best_auc", -1.0)
    return start_epoch, best_auc


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    cfg = FFTConfig()
    p = argparse.ArgumentParser(description="FFT deepfake detector training")
    p.add_argument("--data_dir", type=str, default=cfg.data_dir)
    p.add_argument("--out_dir", type=str, default=cfg.out_dir)
    p.add_argument("--device", type=str, default=cfg.device)
    p.add_argument("--model_arch", type=str, default=cfg.model_arch, choices=["resnet18", "efficientnet_b0"])
    p.add_argument("--loss_fn", type=str, default=cfg.loss_fn, choices=["bce", "focal"])
    p.add_argument("--epochs", type=int, default=cfg.epochs)
    p.add_argument("--batch_size", type=int, default=cfg.batch_size)
    p.add_argument("--val_batch_size", type=int, default=cfg.val_batch_size)
    p.add_argument("--lr", type=float, default=cfg.lr)
    p.add_argument("--weight_decay", type=float, default=cfg.weight_decay)
    p.add_argument("--early_patience", type=int, default=cfg.early_patience)
    p.add_argument("--seed", type=int, default=cfg.seed)
    p.add_argument("--workers", type=int, default=cfg.num_workers)
    p.add_argument("--amp", action="store_true", default=cfg.amp)
    p.add_argument("--no_amp", dest="amp", action="store_false")
    p.add_argument("--channel_mode", type=str, default=cfg.channel_mode, choices=["ycbcr_y", "gray"])
    p.add_argument("--norm_mode", type=str, default=cfg.norm_mode, choices=["dataset", "sample"])
    p.add_argument("--image_size", type=int, default=cfg.image_size)
    p.add_argument("--radial_emphasis", action="store_true", default=cfg.radial_emphasis)
    p.add_argument("--no_radial_emphasis", dest="radial_emphasis", action="store_false")
    p.add_argument("--resume", type=str, default=None)
    return p.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    # Merge args back into config (single source of truth)
    cfg = FFTConfig(
        data_dir=args.data_dir,
        out_dir=args.out_dir,
        image_size=args.image_size,
        channel_mode=args.channel_mode,
        norm_mode=args.norm_mode,
        stats_file=str(Path(args.out_dir) / "fft_stats.json"),
        radial_emphasis=args.radial_emphasis,
        model_arch=args.model_arch,
        loss_fn=args.loss_fn,
        epochs=args.epochs,
        batch_size=args.batch_size,
        val_batch_size=args.val_batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        early_patience=args.early_patience,
        seed=args.seed,
        num_workers=args.workers,
        amp=args.amp,
        resume=args.resume,
        device=args.device,
    )

    set_seed(cfg.seed)

    # Device
    if cfg.device:
        device = torch.device(cfg.device)
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if device.type == "cuda":
        torch.backends.cudnn.benchmark = True
    print(f"Device: {device}")

    out_dir = Path(cfg.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Save effective config for reproducibility
    config_path = out_dir / "fft_run_config.json"
    with open(config_path, "w") as f:
        json.dump(asdict(cfg), f, indent=2)

    # ---- Data ----
    data_dir = Path(cfg.data_dir).resolve()
    paths, labels = collect_paths(data_dir)
    y_int = np.array(labels, dtype=np.int32)

    train_paths, val_paths, train_labels, val_labels = train_test_split(
        paths, labels,
        test_size=cfg.val_split,
        random_state=cfg.seed,
        stratify=y_int,
    )
    print(
        f"Train: {len(train_labels)} | Val: {len(val_labels)} "
        f"(real/fake split by stratification)"
    )

    # Build radial mask once - shared between train/val
    radial_mask = None
    if cfg.radial_emphasis:
        radial_mask = build_radial_emphasis_mask(cfg.image_size, cfg.radial_emphasis_sigma)

    # Dataset stats (computed on train only, no leakage)
    dataset_mean, dataset_std = None, None
    if cfg.norm_mode == "dataset":
        dataset_mean, dataset_std = build_or_load_stats(train_paths, cfg)

    train_loader = build_train_loader(train_paths, train_labels, cfg, dataset_mean, dataset_std, radial_mask)
    val_loader = build_val_loader(val_paths, val_labels, cfg, dataset_mean, dataset_std, radial_mask)

    # ---- Model & optimiser ----
    model = build_model(cfg.model_arch).to(device)
    criterion = build_loss(cfg.loss_fn, cfg.focal_gamma, cfg.focal_alpha)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
    scaler = GradScaler(enabled=(cfg.amp and device.type == "cuda"))

    start_epoch = 0
    best_auc = -1.0
    patience_counter = 0

    # ---- Resume ----
    log_csv = out_dir / "fft_training_log.csv"
    if cfg.resume:
        print(f"Resuming from: {cfg.resume}")
        start_epoch, best_auc = load_checkpoint(cfg.resume, model, optimizer, scaler, device)
        print(f"  -> Resuming from epoch {start_epoch}, best_auc={best_auc:.4f}")
        # Don't wipe the existing log on resume
    else:
        if log_csv.exists():
            log_csv.unlink()

    # ---- Training loop ----
    log_rows = []
    for epoch in range(start_epoch, cfg.epochs):
        tr_loss = train_one_epoch(model, train_loader, criterion, optimizer, scaler, device, cfg.amp)
        metrics = validate(model, val_loader, device, cfg.amp)

        row = {
            "epoch": epoch,
            "train_loss": tr_loss,
            "val_auc": metrics["auc"],
            "val_f1": metrics["f1"],
            "val_acc": metrics["acc"],
            "val_eer": metrics["eer"],
        }
        log_rows.append(row)
        append_csv([row], log_csv)

        print(
            f"[FFT] ep {epoch+1}/{cfg.epochs} | loss={tr_loss:.4f} "
            f"| auc={metrics['auc']:.4f} f1={metrics['f1']:.4f} "
            f"eer={metrics['eer']:.4f} acc={metrics['acc']:.4f}"
        )

        # Best model checkpoint
        auc = metrics["auc"]
        if not np.isnan(auc) and auc > best_auc:
            best_auc = auc
            patience_counter = 0
            torch.save(
                {
                    "model_state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
                    "best_val_auc": best_auc,
                    "arch": cfg.model_arch,
                    "label_real": 0.0,
                    "label_fake": 1.0,
                },
                out_dir / "best_fft_model.pth",
            )
        else:
            patience_counter += 1

        # Latest checkpoint every epoch (safe resume)
        save_checkpoint(
            out_dir / "latest_fft_checkpoint.pth",
            model, optimizer, scaler, epoch, best_auc,
        )

        if patience_counter >= cfg.early_patience:
            print(f"Early stopping: no AUC improvement for {cfg.early_patience} epochs.")
            break

    print(f"Training complete. Best val AUC: {best_auc:.4f}")
    print(f"Checkpoints in: {out_dir}")


if __name__ == "__main__":
    main()
