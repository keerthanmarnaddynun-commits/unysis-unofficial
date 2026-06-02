"""
fusion_scores.py - Branch score I/O, sample_id alignment, and sanity checks.

Supports legacy .npz (probs + labels only) and full format (sample_id, logits, probs, labels).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

LOGIT_EPS = 1e-6


@dataclass
class BranchScores:
    sample_ids: np.ndarray  # shape (N,), dtype=object (str)
    logits: np.ndarray  # float32 (N,)
    probs: np.ndarray  # float32 (N,)
    labels: np.ndarray  # float32 (N,)


@dataclass
class AlignedScores:
    sample_ids: np.ndarray
    labels: np.ndarray
    fft_logits: np.ndarray
    fft_probs: np.ndarray
    spatial_logits: np.ndarray
    spatial_probs: np.ndarray


@dataclass
class AlignmentReport:
    n_fft: int = 0
    n_spatial: int = 0
    n_joined: int = 0
    n_fft_only: int = 0
    n_spatial_only: int = 0
    duplicate_fft: int = 0
    duplicate_spatial: int = 0
    label_mismatches: int = 0
    used_index_fallback: bool = False
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def path_to_sample_id(path: Path, data_dir: Optional[Path] = None) -> str:
    """Stable relative path id, e.g. real/face001.jpg."""
    p = path.resolve()
    if data_dir is not None:
        try:
            return p.relative_to(data_dir.resolve()).as_posix()
        except ValueError:
            pass
    # fallback: posix path from drive root
    parts = p.parts
    if "real" in parts or "fake" in parts:
        for i, part in enumerate(parts):
            if part in ("real", "fake"):
                return "/".join(parts[i:]).replace("\\", "/")
    return p.as_posix()


def logit_from_prob(probs: np.ndarray, eps: float = LOGIT_EPS) -> np.ndarray:
    p = np.clip(probs.astype(np.float64), eps, 1.0 - eps)
    return np.log(p / (1.0 - p)).astype(np.float32)


def prob_from_logit(logits: np.ndarray) -> np.ndarray:
    return (1.0 / (1.0 + np.exp(-logits.astype(np.float64)))).astype(np.float32)


def save_branch_scores(
    path: str | Path,
    sample_ids: np.ndarray,
    logits: np.ndarray,
    labels: np.ndarray,
    probs: Optional[np.ndarray] = None,
) -> None:
    """Save branch scores (.npz). probs derived from logits if omitted."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logits = np.asarray(logits, dtype=np.float32).reshape(-1)
    labels = np.asarray(labels, dtype=np.float32).reshape(-1)
    ids = np.asarray(sample_ids).reshape(-1)
    if probs is None:
        probs = prob_from_logit(logits)
    else:
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
    if not (len(ids) == len(logits) == len(labels) == len(probs)):
        raise ValueError("sample_ids, logits, probs, and labels must have the same length.")
    np.savez(
        path,
        sample_id=ids,
        logits=logits,
        probs=probs,
        labels=labels,
    )
    print(f"Scores saved to {path} ({len(ids)} samples, with sample_id + logits + probs)")


def load_branch_scores(path: str | Path) -> BranchScores:
    """Load branch scores; supports legacy files without sample_id or logits."""
    path = Path(path)
    data = np.load(path, allow_pickle=True)
    warnings: List[str] = []

    if "labels" not in data:
        raise KeyError(f"{path}: missing 'labels' array.")

    labels = data["labels"].astype(np.float32).reshape(-1)
    n = len(labels)

    if "probs" in data:
        probs = data["probs"].astype(np.float32).reshape(-1)
    else:
        probs = None

    if "logits" in data:
        logits = data["logits"].astype(np.float32).reshape(-1)
        if probs is None:
            probs = prob_from_logit(logits)
    elif probs is not None:
        logits = logit_from_prob(probs)
        warnings.append("logits reconstructed from probs")
    else:
        raise KeyError(f"{path}: need 'probs' and/or 'logits'.")

    if "sample_id" in data:
        sample_ids = np.asarray(data["sample_id"]).reshape(-1)
        sample_ids = np.array([str(s) for s in sample_ids], dtype=object)
    else:
        sample_ids = np.array([f"row_{i:06d}" for i in range(n)], dtype=object)
        warnings.append(
            "no sample_id in file - using row_000000..; re-export scores with sample_id for safe fusion"
        )

    if len(sample_ids) != n or len(logits) != n or len(probs) != n:
        raise ValueError(f"{path}: array length mismatch.")

    for w in warnings:
        print(f"[load {path.name}] WARNING: {w}")

    return BranchScores(sample_ids=sample_ids, logits=logits, probs=probs, labels=labels)


def _check_duplicates(sample_ids: np.ndarray, branch: str) -> int:
    _, counts = np.unique(sample_ids, return_counts=True)
    return int(np.sum(counts > 1))


def align_branches(
    fft: BranchScores,
    spatial: BranchScores,
    *,
    allow_index_fallback: bool = True,
) -> Tuple[AlignedScores, AlignmentReport]:
    """
    Inner-join FFT and spatial scores on sample_id.
    If both lack real sample_ids (row_*), falls back to index order when lengths match.
    """
    report = AlignmentReport(
        n_fft=len(fft.sample_ids),
        n_spatial=len(spatial.sample_ids),
    )
    report.duplicate_fft = _check_duplicates(fft.sample_ids, "fft")
    report.duplicate_spatial = _check_duplicates(spatial.sample_ids, "spatial")
    if report.duplicate_fft:
        report.warnings.append(f"FFT has {report.duplicate_fft} duplicate sample_id values")
    if report.duplicate_spatial:
        report.warnings.append(
            f"Spatial has {report.duplicate_spatial} duplicate sample_id values"
        )

    fft_legacy = bool(np.all([str(s).startswith("row_") for s in fft.sample_ids]))
    spatial_legacy = bool(np.all([str(s).startswith("row_") for s in spatial.sample_ids]))

    if fft_legacy and spatial_legacy and len(fft.sample_ids) == len(spatial.sample_ids):
        if allow_index_fallback:
            report.used_index_fallback = True
            report.warnings.append(
                "Both score files use row_* ids - aligning by row order (legacy). "
                "Re-export with sample_id for production fusion."
            )
            if not np.allclose(fft.labels, spatial.labels):
                mism = int(np.sum(fft.labels != spatial.labels))
                report.label_mismatches = mism
                raise ValueError(
                    f"Label mismatch under index alignment: {mism} rows differ. "
                    "Regenerate scores on the same val split."
                )
            report.n_joined = len(fft.sample_ids)
            aligned = AlignedScores(
                sample_ids=fft.sample_ids.copy(),
                labels=fft.labels.copy(),
                fft_logits=fft.logits.copy(),
                fft_probs=fft.probs.copy(),
                spatial_logits=spatial.logits.copy(),
                spatial_probs=spatial.probs.copy(),
            )
            return aligned, report

    # Map sample_id -> index
    def build_map(scores: BranchScores) -> Dict[str, int]:
        m: Dict[str, int] = {}
        for i, sid in enumerate(scores.sample_ids):
            key = str(sid)
            if key in m:
                report.warnings.append(f"duplicate sample_id '{key}' - keeping first occurrence")
            else:
                m[key] = i
        return m

    fft_map = build_map(fft)
    spatial_map = build_map(spatial)
    common = sorted(set(fft_map) & set(spatial_map))
    fft_only = set(fft_map) - set(spatial_map)
    spatial_only = set(spatial_map) - set(fft_map)

    report.n_joined = len(common)
    report.n_fft_only = len(fft_only)
    report.n_spatial_only = len(spatial_only)

    if fft_only:
        report.warnings.append(f"{len(fft_only)} FFT-only samples dropped from fusion")
    if spatial_only:
        report.warnings.append(f"{len(spatial_only)} spatial-only samples dropped from fusion")

    if report.n_joined == 0:
        raise ValueError("No overlapping sample_id between FFT and spatial score files.")

    idx_f = [fft_map[s] for s in common]
    idx_s = [spatial_map[s] for s in common]

    labels_f = fft.labels[idx_f]
    labels_s = spatial.labels[idx_s]
    mism = labels_f != labels_s
    report.label_mismatches = int(np.sum(mism))
    if report.label_mismatches:
        bad = [common[i] for i in np.where(mism)[0][:5]]
        raise ValueError(
            f"Label mismatch on {report.label_mismatches} shared samples. "
            f"Examples: {bad}"
        )

    aligned = AlignedScores(
        sample_ids=np.array(common, dtype=object),
        labels=labels_f.copy(),
        fft_logits=fft.logits[idx_f].copy(),
        fft_probs=fft.probs[idx_f].copy(),
        spatial_logits=spatial.logits[idx_s].copy(),
        spatial_probs=spatial.probs[idx_s].copy(),
    )
    return aligned, report


def sanity_check_scores(scores: BranchScores, name: str) -> List[str]:
    """Return list of warnings (empty if clean)."""
    issues: List[str] = []
    n = len(scores.labels)
    if n == 0:
        issues.append(f"{name}: empty score file")
        return issues
    if np.any(np.isnan(scores.logits)) or np.any(np.isnan(scores.probs)):
        issues.append(f"{name}: NaN in logits or probs")
    if len(np.unique(scores.labels)) < 2:
        issues.append(f"{name}: only one class present - AUC/EER undefined")
    uniq, counts = np.unique(scores.sample_ids, return_counts=True)
    if np.any(counts > 1):
        issues.append(f"{name}: {int(np.sum(counts > 1))} duplicate sample_ids")
    # prob/logit consistency
    recon = prob_from_logit(scores.logits)
    if np.max(np.abs(recon - scores.probs)) > 1e-2:
        issues.append(f"{name}: probs differ from sigmoid(logits) by >0.01 (max drift)")
    return issues


def save_alignment_report(report: AlignmentReport, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)


# Backward-compatible helpers used by older code paths
def load_scores(path: str | Path) -> Tuple[np.ndarray, np.ndarray]:
    """Legacy: return (probs, labels) only."""
    b = load_branch_scores(path)
    return b.probs, b.labels


def save_scores(
    probs: np.ndarray,
    labels: np.ndarray,
    path: str | Path,
    sample_ids: Optional[np.ndarray] = None,
    logits: Optional[np.ndarray] = None,
) -> None:
    """Legacy-compatible save; prefers full format when sample_ids/logits supplied."""
    n = len(labels)
    if sample_ids is None:
        sample_ids = np.array([f"row_{i:06d}" for i in range(n)], dtype=object)
    if logits is None:
        logits = logit_from_prob(np.asarray(probs, dtype=np.float32))
    save_branch_scores(path, sample_ids, logits, labels, probs=probs)
