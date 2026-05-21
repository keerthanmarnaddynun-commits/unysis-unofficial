"""
fft_config.py - Centralized configuration for the FFT deepfake detection pipeline.

All preprocessing, training, and dataloader settings live here.
Override via argparse in train_fft.py; this module provides the defaults.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class FFTConfig:
    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    data_dir: str = "final_dataset_aligned"
    out_dir: str = "fft_output"

    # ------------------------------------------------------------------ #
    # Preprocessing
    # ------------------------------------------------------------------ #
    image_size: int = 224
    # Channel mode: "ycbcr_y" (default) or "gray"
    channel_mode: str = "ycbcr_y"
    # Normalization: "dataset" (recommended) or "sample"
    norm_mode: str = "dataset"
    # Path for saving/loading dataset-level FFT stats (mean/std)
    stats_file: str = "fft_output/fft_stats.json"
    # Optional radial high-freq emphasis: enable and control sigma
    radial_emphasis: bool = True
    radial_emphasis_sigma: float = 0.3  # fraction of image half-diagonal; smaller = more selective

    # ------------------------------------------------------------------ #
    # Model
    # ------------------------------------------------------------------ #
    # "resnet18" (default) or "efficientnet_b0"
    model_arch: str = "resnet18"
    # "bce" (default) or "focal"
    loss_fn: str = "bce"
    focal_gamma: float = 2.0
    focal_alpha: float = 0.75

    # ------------------------------------------------------------------ #
    # Training
    # ------------------------------------------------------------------ #
    seed: int = 42
    epochs: int = 40
    batch_size: int = 64
    val_batch_size: int = 64
    lr: float = 1e-4
    weight_decay: float = 1e-4
    early_patience: int = 7
    val_split: float = 0.2

    # ------------------------------------------------------------------ #
    # DataLoader (Windows-safe defaults)
    # ------------------------------------------------------------------ #
    num_workers: int = 4
    pin_memory: bool = True
    persistent_workers: bool = True
    prefetch_factor: int = 2

    # ------------------------------------------------------------------ #
    # Mixed precision
    # ------------------------------------------------------------------ #
    amp: bool = True

    # ------------------------------------------------------------------ #
    # Resume
    # ------------------------------------------------------------------ #
    resume: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Device
    # ------------------------------------------------------------------ #
    device: Optional[str] = None  # None = auto


# Module-level singleton - import and override fields as needed
DEFAULT_CONFIG = FFTConfig()
