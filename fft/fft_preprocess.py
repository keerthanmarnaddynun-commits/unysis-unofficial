"""
fft_preprocess.py - Reusable FFT preprocessing module.

Pipeline:
  1. Read image -> convert to Y-channel (YCbCr) or grayscale
  2. Resize to image_size x image_size
  3. Cast to float32
  4. 2D FFT -> fftshift -> magnitude -> log(1 + magnitude)
  5. Optional: soft radial high-frequency emphasis
  6. Normalize (dataset-level or sample-level)

All settings are driven by FFTConfig from fft_config.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


# ---------------------------------------------------------------------------
# Core transform (operates on numpy arrays)
# ---------------------------------------------------------------------------

def image_to_fft_spectrum(
    img_path: str | Path,
    image_size: int = 224,
    channel_mode: str = "ycbcr_y",
) -> np.ndarray:
    """
    Load image and convert to log-magnitude FFT spectrum.

    Returns:
        spectrum: float32 ndarray of shape (image_size, image_size), unnormalised.
    """
    with Image.open(img_path) as img:
        img = img.convert("RGB")
        img = img.resize((image_size, image_size), Image.BILINEAR)

        if channel_mode == "ycbcr_y":
            # Extract luminance channel only - contains most structural artifacts
            arr = np.array(img.convert("YCbCr"), dtype=np.float32)[..., 0]
        else:
            # Grayscale fallback
            arr = np.array(img.convert("L"), dtype=np.float32)

    # 2D FFT -> center zero-frequency -> magnitude -> log-scale
    spectrum = np.fft.fft2(arr)
    spectrum = np.fft.fftshift(spectrum)
    magnitude = np.abs(spectrum)
    log_mag = np.log1p(magnitude)  # log(1 + magnitude)

    return log_mag.astype(np.float32)


# ---------------------------------------------------------------------------
# Optional radial high-frequency emphasis
# ---------------------------------------------------------------------------

def build_radial_emphasis_mask(
    size: int,
    sigma: float = 0.3,
) -> np.ndarray:
    """
    Build a soft radial emphasis mask that attenuates the DC center
    and boosts high-frequency rings.

    sigma: fraction of the half-diagonal that defines the Gaussian fall-off.
            Smaller -> sharper attenuation of the center.
    Returns float32 mask of shape (size, size).
    """
    cy, cx = size // 2, size // 2
    ys, xs = np.ogrid[:size, :size]
    dist = np.sqrt((ys - cy) ** 2 + (xs - cx) ** 2)
    max_dist = np.sqrt(cy ** 2 + cx ** 2)
    # Normalize distances to [0, 1]
    dist_norm = dist / (max_dist + 1e-8)
    # Gaussian centre-attenuation: low weight at centre, higher at edges
    mask = 1.0 - np.exp(-((dist_norm / sigma) ** 2))
    return mask.astype(np.float32)


def apply_radial_emphasis(spectrum: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Element-wise multiply spectrum with emphasis mask."""
    return spectrum * mask


# ---------------------------------------------------------------------------
# Sample-level normalization
# ---------------------------------------------------------------------------

def normalize_sample(spectrum: np.ndarray) -> np.ndarray:
    """Zero-mean, unit-std normalization per individual spectrum."""
    mu = spectrum.mean()
    std = spectrum.std() + 1e-8
    return (spectrum - mu) / std


# ---------------------------------------------------------------------------
# Dataset-level stats: compute, save, load
# ---------------------------------------------------------------------------

def compute_dataset_stats(
    spectra: list[np.ndarray],
) -> Tuple[float, float]:
    """Compute global mean and std from a list of spectra arrays."""
    all_vals = np.concatenate([s.ravel() for s in spectra])
    return float(all_vals.mean()), float(all_vals.std() + 1e-8)


def save_stats(mean: float, std: float, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"mean": mean, "std": std}, f)


def load_stats(path: str | Path) -> Tuple[float, float]:
    with open(path, "r") as f:
        d = json.load(f)
    return float(d["mean"]), float(d["std"])


def normalize_dataset(spectrum: np.ndarray, mean: float, std: float) -> np.ndarray:
    return (spectrum - mean) / std


# ---------------------------------------------------------------------------
# Full preprocessing function (single image entry point)
# ---------------------------------------------------------------------------

def preprocess_image(
    img_path: str | Path,
    image_size: int,
    channel_mode: str,
    norm_mode: str,
    dataset_mean: Optional[float] = None,
    dataset_std: Optional[float] = None,
    use_radial_emphasis: bool = False,
    radial_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    Full FFT preprocessing pipeline for a single image.

    Returns a normalised float32 spectrum of shape (image_size, image_size).
    Add a channel dimension when passing to PyTorch (unsqueeze(0)).
    """
    spectrum = image_to_fft_spectrum(img_path, image_size, channel_mode)

    if use_radial_emphasis and radial_mask is not None:
        spectrum = apply_radial_emphasis(spectrum, radial_mask)

    if norm_mode == "sample":
        spectrum = normalize_sample(spectrum)
    elif norm_mode == "dataset":
        if dataset_mean is None or dataset_std is None:
            raise ValueError("dataset_mean and dataset_std must be provided for dataset-level norm.")
        spectrum = normalize_dataset(spectrum, dataset_mean, dataset_std)

    return spectrum
