"""
fft_dataset.py - PyTorch Dataset and DataLoader builders for the FFT pipeline.

Responsibilities:
  - Index real/ and fake/ image paths.
  - Compute dataset-level FFT stats on the training split (no leakage).
  - Provide FFTDataset that returns (1-channel tensor, label).
  - Build train/val DataLoaders with Windows-safe settings.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from fft_config import FFTConfig
from fft_preprocess import (
    build_radial_emphasis_mask,
    compute_dataset_stats,
    image_to_fft_spectrum,
    apply_radial_emphasis,
    load_stats,
    preprocess_image,
    save_stats,
)


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


# ---------------------------------------------------------------------------
# Path collection
# ---------------------------------------------------------------------------

def collect_paths(data_dir: Path) -> Tuple[List[Path], List[float]]:
    """Collect image paths from real/ and fake/ subdirectories."""
    real_dir = data_dir / "real"
    fake_dir = data_dir / "fake"
    paths: List[Path] = []
    labels: List[float] = []

    for d, label in [(real_dir, 0.0), (fake_dir, 1.0)]:
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*")):
            if p.suffix.lower() in SUPPORTED_EXTS:
                paths.append(p)
                labels.append(label)

    if not paths:
        raise FileNotFoundError(f"No images found under {real_dir} or {fake_dir}")

    return paths, labels


# ---------------------------------------------------------------------------
# Dataset-level stats: compute on training split only
# ---------------------------------------------------------------------------

def build_or_load_stats(
    train_paths: List[Path],
    cfg: FFTConfig,
) -> Tuple[float, float]:
    """
    Load saved FFT stats if they exist, otherwise compute from training paths
    and save for future runs. This prevents leakage into the validation set.
    """
    stats_path = Path(cfg.stats_file)

    if stats_path.exists():
        print(f"Loading FFT stats from {stats_path}")
        return load_stats(stats_path)

    print(f"Computing FFT stats on {len(train_paths)} training images...")
    spectra = []
    radial_mask = None
    if cfg.radial_emphasis:
        radial_mask = build_radial_emphasis_mask(cfg.image_size, cfg.radial_emphasis_sigma)

    for p in tqdm(train_paths, desc="FFT stats", leave=False):
        try:
            s = image_to_fft_spectrum(p, cfg.image_size, cfg.channel_mode)
            if cfg.radial_emphasis and radial_mask is not None:
                s = apply_radial_emphasis(s, radial_mask)
            spectra.append(s)
        except Exception:
            continue

    mean, std = compute_dataset_stats(spectra)
    save_stats(mean, std, stats_path)
    print(f"FFT stats: mean={mean:.4f}, std={std:.4f} -> saved to {stats_path}")
    return mean, std


# ---------------------------------------------------------------------------
# Dataset class
# ---------------------------------------------------------------------------

class FFTDataset(Dataset):
    """
    Returns (tensor[1, H, W], label_tensor) for each image.
    Labels: real=0.0, fake=1.0.
    """

    def __init__(
        self,
        paths: List[Path],
        labels: List[float],
        cfg: FFTConfig,
        dataset_mean: Optional[float] = None,
        dataset_std: Optional[float] = None,
        radial_mask: Optional[np.ndarray] = None,
    ) -> None:
        self.paths = paths
        self.labels = labels
        self.cfg = cfg
        self.dataset_mean = dataset_mean
        self.dataset_std = dataset_std
        self.radial_mask = radial_mask

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        spectrum = preprocess_image(
            self.paths[idx],
            image_size=self.cfg.image_size,
            channel_mode=self.cfg.channel_mode,
            norm_mode=self.cfg.norm_mode,
            dataset_mean=self.dataset_mean,
            dataset_std=self.dataset_std,
            use_radial_emphasis=self.cfg.radial_emphasis,
            radial_mask=self.radial_mask,
        )
        # Add channel dimension: (1, H, W)
        tensor = torch.from_numpy(spectrum).unsqueeze(0)
        label = torch.tensor(self.labels[idx], dtype=torch.float32)
        return tensor, label


# ---------------------------------------------------------------------------
# DataLoader builders
# ---------------------------------------------------------------------------

def build_train_loader(
    paths: List[Path],
    labels: List[float],
    cfg: FFTConfig,
    dataset_mean: Optional[float],
    dataset_std: Optional[float],
    radial_mask: Optional[np.ndarray],
) -> DataLoader:
    ds = FFTDataset(paths, labels, cfg, dataset_mean, dataset_std, radial_mask)
    pf = cfg.prefetch_factor if cfg.num_workers > 0 else None
    return DataLoader(
        ds,
        batch_size=cfg.batch_size,
        shuffle=True,
        num_workers=cfg.num_workers,
        pin_memory=cfg.pin_memory,
        persistent_workers=cfg.persistent_workers and cfg.num_workers > 0,
        prefetch_factor=pf,
        drop_last=False,
    )


def build_val_loader(
    paths: List[Path],
    labels: List[float],
    cfg: FFTConfig,
    dataset_mean: Optional[float],
    dataset_std: Optional[float],
    radial_mask: Optional[np.ndarray],
) -> DataLoader:
    ds = FFTDataset(paths, labels, cfg, dataset_mean, dataset_std, radial_mask)
    pf = cfg.prefetch_factor if cfg.num_workers > 0 else None
    return DataLoader(
        ds,
        batch_size=cfg.val_batch_size,
        shuffle=False,
        num_workers=cfg.num_workers,
        pin_memory=cfg.pin_memory,
        persistent_workers=cfg.persistent_workers and cfg.num_workers > 0,
        prefetch_factor=pf,
    )
