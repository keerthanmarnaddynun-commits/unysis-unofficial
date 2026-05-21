#!/usr/bin/env python3
"""Inference script for EfficientNetB4Binary model.

Usage examples (run from the repository root ``D:\\forsen``):

    python test_cnn.py --image path/to/image.jpg
    python test_cnn.py --input_dir path/to/folder
    python test_cnn.py --diagnose
    python test_cnn.py --input_dir test_images --face_crop --skip_no_face
    python test_cnn.py --diagnose --face_crop --invert_output
    python test_cnn.py --input_dir test_images --face_crop --save_preprocessed debug_preprocessed/

Label convention (from train_deepfake_detection.py):
    REAL = 0, FAKE = 1.  sigmoid(logit) = P(fake).

Training/validation images in final_dataset_aligned are already 380x380 MTCNN-aligned
face crops. test_images are typically full-frame images and need --face_crop (or they
must be pre-aligned to 380x380).

Recommended Python (training env on this machine)::

    D:\\envs\\gpu_env\\python.exe test_cnn.py --diagnose --face_crop
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import albumentations as A
import numpy as np
import torch
import torch.nn as nn
from albumentations.pytorch import ToTensorV2
from PIL import Image
from sklearn.model_selection import train_test_split

from train_deepfake_detection import (
    EfficientNetB4Binary,
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_tta_post_normalize,
    collect_paths,
)

# ---------------------------------------------------------------------------
# Pre-processing – identical to validation transform in training script
# ---------------------------------------------------------------------------

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
DEFAULT_MODEL_PATH = Path("training_output/best_model.pth")
DEFAULT_ALIGNED_DIR = Path("final_dataset_aligned")
DEFAULT_TEST_DIR = Path("test_images")
DIAGNOSE_N_PER_GROUP = 10
VAL_SPLIT_SEED = 42


@dataclass
class PreprocessResult:
    image_np: np.ndarray
    face_detected: Optional[bool]  # None = face_crop not used
    source_size: Tuple[int, int]
    output_size: Tuple[int, int]


@dataclass
class InferenceResult:
    path: Path
    logit: float
    prob_fake: float
    pred_fake: int
    pred_label: str
    face_detected: Optional[bool]


_MTCNN = None


def get_mtcnn(device: torch.device):
    global _MTCNN
    if _MTCNN is None:
        try:
            from facenet_pytorch import MTCNN
        except ImportError as exc:
            raise ImportError(
                "facenet-pytorch is required for --face_crop. "
                "Install in your training env, e.g. pip install facenet-pytorch. "
                "On this machine, use: D:\\envs\\gpu_env\\python.exe"
            ) from exc

        _MTCNN = MTCNN(
            image_size=160,
            margin=0,
            min_face_size=20,
            thresholds=[0.6, 0.7, 0.7],
            factor=0.709,
            post_process=False,
            device=str(device),
            keep_all=True,
        )
    return _MTCNN


def detect_and_align_face(
    pil_rgb: Image.Image,
    device: torch.device,
    out_size: int = 380,
    margin_frac: float = 0.30,
) -> Optional[np.ndarray]:
    """Detect largest face, align with 5-point landmarks, return RGB uint8 (out_size x out_size)."""
    mtcnn = get_mtcnn(device)
    import cv2

    boxes, _probs, landmarks = mtcnn.detect(pil_rgb, landmarks=True)
    if boxes is None or landmarks is None or len(boxes) == 0:
        return None

    boxes = np.asarray(boxes, dtype=np.float32)
    landmarks = np.asarray(landmarks, dtype=np.float32)

    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    idx = int(np.argmax(areas))
    box = boxes[idx]
    lm = landmarks[idx]

    img = np.asarray(pil_rgb, dtype=np.uint8)
    h, w = img.shape[:2]

    x1, y1, x2, y2 = box
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    new_w = bw * (1.0 + 2.0 * margin_frac)
    new_h = bh * (1.0 + 2.0 * margin_frac)

    nx1 = int(max(0, np.floor(cx - new_w / 2.0)))
    ny1 = int(max(0, np.floor(cy - new_h / 2.0)))
    nx2 = int(min(w, np.ceil(cx + new_w / 2.0)))
    ny2 = int(min(h, np.ceil(cy + new_h / 2.0)))
    if nx2 <= nx1 or ny2 <= ny1:
        return None

    crop = img[ny1:ny2, nx1:nx2].copy()
    lm_crop = lm.copy()
    lm_crop[:, 0] -= float(nx1)
    lm_crop[:, 1] -= float(ny1)

    template_112 = np.array(
        [
            [38.2946, 51.6963],
            [73.5318, 51.5014],
            [56.0252, 71.7366],
            [41.5493, 92.3655],
            [70.7299, 92.2041],
        ],
        dtype=np.float32,
    )
    dst = template_112 * (float(out_size) / 112.0)
    M, _inliers = cv2.estimateAffinePartial2D(
        lm_crop.astype(np.float32),
        dst.astype(np.float32),
        method=cv2.LMEDS,
    )
    if M is None:
        return None

    return cv2.warpAffine(
        crop,
        M,
        (out_size, out_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def get_transform() -> A.Compose:
    """Validation transform: Normalize + ToTensorV2 only (matches build_val_dataloader)."""
    return build_tta_post_normalize()


def load_image_pil(path: Path) -> Image.Image:
    try:
        with Image.open(path) as im:
            return im.convert("RGB")
    except Exception as exc:
        raise RuntimeError(f"Failed to read image {path}: {exc}") from exc


def _resize_bilinear(pil_img: Image.Image, size: int) -> np.ndarray:
    try:
        resample = Image.Resampling.BILINEAR
    except AttributeError:
        resample = Image.BILINEAR
    return np.array(pil_img.resize((size, size), resample=resample), dtype=np.uint8)


def preprocess_image(
    pil_img: Image.Image,
    *,
    device: torch.device,
    face_crop: bool,
    skip_no_face: bool,
    resize_if_not_380: bool,
    align_size: int = 380,
) -> Optional[PreprocessResult]:
    """Build uint8 HWC RGB array fed to the CNN (before Normalize)."""
    source_size = pil_img.size  # (W, H)

    if face_crop:
        aligned = detect_and_align_face(pil_img, device, out_size=align_size, margin_frac=0.30)
        if aligned is not None:
            h, w = aligned.shape[:2]
            return PreprocessResult(
                image_np=aligned,
                face_detected=True,
                source_size=source_size,
                output_size=(w, h),
            )
        if skip_no_face:
            return None
        img_np = _resize_bilinear(pil_img, align_size)
        h, w = img_np.shape[:2]
        return PreprocessResult(
            image_np=img_np,
            face_detected=False,
            source_size=source_size,
            output_size=(w, h),
        )

    img_np = np.array(pil_img, dtype=np.uint8)
    h, w = img_np.shape[:2]
    if resize_if_not_380 and (h != align_size or w != align_size):
        img_np = _resize_bilinear(pil_img, align_size)
        h, w = img_np.shape[:2]
    return PreprocessResult(
        image_np=img_np,
        face_detected=None,
        source_size=source_size,
        output_size=(w, h),
    )


def load_model(model_path: Path, device: torch.device) -> Tuple[nn.Module, Dict]:
    """Load checkpoint; returns (model, metadata dict)."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    model = EfficientNetB4Binary(pretrained=False)
    ckpt = torch.load(model_path, map_location=device, weights_only=False)  # full checkpoint dict
    meta: Dict = {}
    if isinstance(ckpt, dict):
        for meta_key in ("best_val_auc", "threshold", "architecture", "label_real", "label_fake"):
            if meta_key in ckpt:
                meta[meta_key] = ckpt[meta_key]
        if "model_state_dict" in ckpt:
            state_dict = ckpt["model_state_dict"]
        elif "model" in ckpt:
            state_dict = ckpt["model"]
        else:
            state_dict = ckpt
    else:
        state_dict = ckpt

    model.load_state_dict(state_dict, strict=True)
    model.to(device)
    model.eval()
    return model, meta


@torch.no_grad()
def predict_logit(
    model: nn.Module,
    device: torch.device,
    image_np: np.ndarray,
    transform: A.Compose,
    debug: bool = False,
) -> float:
    """Single forward pass; matches validate_batched (no TTA)."""
    aug = transform(image=image_np)
    tensor = aug["image"].unsqueeze(0).to(device, non_blocking=True).float()
    if debug:
        print(
            f"  [DEBUG] tensor min={tensor.min().item():.3f}, "
            f"max={tensor.max().item():.3f}, mean={tensor.mean().item():.3f}, "
            f"shape={tuple(tensor.shape)}"
        )
    with torch.amp.autocast("cuda", enabled=(device.type == "cuda")):
        logit = model(tensor)
    return float(logit.view(-1).item())


def logit_to_fake_prob(logit: float, invert_output: bool = False) -> float:
    prob = 1.0 / (1.0 + np.exp(-logit))
    return float(1.0 - prob) if invert_output else float(prob)


def prob_to_pred(prob_fake: float, threshold: float = 0.5) -> int:
    return 1 if prob_fake >= threshold else 0


def infer_one(
    path: Path,
    pil_img: Image.Image,
    model: nn.Module,
    device: torch.device,
    transform: A.Compose,
    *,
    face_crop: bool,
    skip_no_face: bool,
    resize_if_not_380: bool,
    invert_output: bool,
    threshold: float,
    debug: bool = False,
) -> Optional[InferenceResult]:
    prep = preprocess_image(
        pil_img,
        device=device,
        face_crop=face_crop,
        skip_no_face=skip_no_face,
        resize_if_not_380=resize_if_not_380,
    )
    if prep is None:
        return None

    logit = predict_logit(model, device, prep.image_np, transform, debug=debug)
    prob_fake = logit_to_fake_prob(logit, invert_output=invert_output)
    pred_fake = prob_to_pred(prob_fake, threshold)
    label = "fake" if pred_fake == 1 else "real"
    return InferenceResult(
        path=path,
        logit=logit,
        prob_fake=prob_fake,
        pred_fake=pred_fake,
        pred_label=label,
        face_detected=prep.face_detected,
    )


def save_preprocessed_image(image_np: np.ndarray, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image_np).save(out_path, quality=95)


def iter_image_paths(root: Path) -> List[Path]:
    return sorted(p for p in root.rglob("*") if p.suffix.lower() in SUPPORTED_EXTS)


def label_from_path(path: Path) -> Optional[int]:
    """Infer ground truth from path: fake=1, real=0."""
    parts = {part.lower() for part in path.parts}
    if "fake" in parts:
        return 1
    if "real" in parts:
        return 0
    return None


def sample_paths_from_dir(directory: Path, n: int, rng: random.Random) -> List[Path]:
    paths = iter_image_paths(directory)
    if not paths:
        return []
    if len(paths) <= n:
        return paths
    return rng.sample(paths, n)


def sample_val_aligned_paths(
    data_dir: Path,
    n_real: int,
    n_fake: int,
    seed: int,
) -> Tuple[List[Path], List[int]]:
    """Same val split as training (seed=42, 20% holdout)."""
    paths, labels = collect_paths(data_dir)
    y_int = np.asarray(labels, dtype=np.int32)
    _train_p, val_p, _train_y, val_y = train_test_split(
        paths,
        labels,
        test_size=0.2,
        random_state=seed,
        stratify=y_int,
    )
    rng = random.Random(seed + 999)
    real_paths = [p for p, y in zip(val_p, val_y) if y < 0.5]
    fake_paths = [p for p, y in zip(val_p, val_y) if y >= 0.5]
    chosen: List[Path] = []
    chosen_labels: List[int] = []
    real_pick = rng.sample(real_paths, min(n_real, len(real_paths))) if real_paths else []
    fake_pick = rng.sample(fake_paths, min(n_fake, len(fake_paths))) if fake_paths else []
    for p in real_pick:
        chosen.append(p)
        chosen_labels.append(0)
    for p in fake_pick:
        chosen.append(p)
        chosen_labels.append(1)
    return chosen, chosen_labels


def compute_group_metrics(
    y_true: Sequence[int],
    probs: Sequence[float],
    preds: Sequence[int],
) -> Dict[str, float]:
    y = np.asarray(y_true, dtype=np.int32)
    p = np.asarray(probs, dtype=np.float64)
    pr = np.asarray(preds, dtype=np.int32)
    if len(y) == 0:
        return {"n": 0, "acc": float("nan"), "mean_prob": float("nan"), "min_prob": float("nan"), "max_prob": float("nan")}

    acc = float(np.mean(pr == y))
    return {
        "n": len(y),
        "acc": acc,
        "mean_prob": float(np.mean(p)),
        "min_prob": float(np.min(p)),
        "max_prob": float(np.max(p)),
    }


def print_confusion_summary(y_true: List[int], y_pred: List[int], title: str) -> None:
    if not y_true:
        print(f"\n{title}: no labeled samples.")
        return
    y_true_np = np.array(y_true, dtype=np.int32)
    y_pred_np = np.array(y_pred, dtype=np.int32)
    tp = int(np.sum((y_true_np == 1) & (y_pred_np == 1)))
    tn = int(np.sum((y_true_np == 0) & (y_pred_np == 0)))
    fp = int(np.sum((y_true_np == 0) & (y_pred_np == 1)))
    fn = int(np.sum((y_true_np == 1) & (y_pred_np == 0)))
    total = len(y_true)
    acc = (tp + tn) / total
    print(f"\n{title}")
    print(f"  Total: {total} | Accuracy: {acc:.4f} | TP={tp} TN={tn} FP={fp} FN={fn}")


def print_group_diagnosis(
    group_name: str,
    paths: List[Path],
    y_true: List[int],
    results: List[InferenceResult],
    *,
    invert_output: bool,
    threshold: float,
) -> None:
    print(f"\n{'=' * 72}")
    print(f"GROUP: {group_name}  (n={len(results)}, labeled={len(y_true)})")
    print(f"{'=' * 72}")

    if not results:
        print("  (no images processed)")
        return

    probs = [r.prob_fake for r in results]
    preds = [r.pred_fake for r in results]
    m = compute_group_metrics(y_true, probs, preds)
    print(
        f"  fake_prob: mean={m['mean_prob']:.4f} min={m['min_prob']:.4f} max={m['max_prob']:.4f}"
    )
    if y_true:
        print(f"  accuracy (threshold={threshold}): {m['acc']:.4f}")
        n_correct = sum(1 for yt, pr in zip(y_true, preds) if yt == pr)
        print(f"  correct: {n_correct}/{len(y_true)}")

    # Inverted interpretation (test label reversal hypothesis)
    inv_probs = [1.0 - p for p in probs]
    inv_preds = [1 - pr for pr in preds]
    m_inv = compute_group_metrics(y_true, inv_probs, inv_preds)
    if y_true:
        print(
            f"  IF INVERTED: mean_fake_prob={m_inv['mean_prob']:.4f} "
            f"accuracy={m_inv['acc']:.4f}"
        )

    print("\n  Per-image (filename | gt | fake_prob | pred | logit):")
    for r, yt in zip(results, y_true if y_true else [None] * len(results)):
        gt_s = ("real" if yt == 0 else "fake") if yt is not None else "?"
        face_s = ""
        if r.face_detected is True:
            face_s = " [face_ok]"
        elif r.face_detected is False:
            face_s = " [no_face,fallback_resize]"
        print(
            f"    {r.path.name:40s} gt={gt_s:4s} prob={r.prob_fake:.4f} "
            f"pred={r.pred_label:4s} logit={r.logit:+.3f}{face_s}"
        )


def inspect_image_sizes(paths: List[Path], label: str, max_show: int = 5) -> None:
    sizes = []
    for p in paths[:max_show]:
        try:
            with Image.open(p) as im:
                sizes.append((p.name, im.size))
        except Exception:
            sizes.append((p.name, ("?", "?")))
    print(f"\n  Sample sizes ({label}, up to {max_show}):")
    for name, sz in sizes:
        print(f"    {name}: {sz[0]}x{sz[1]}")


def run_diagnose(args: argparse.Namespace) -> int:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = Path(args.model_path).expanduser().resolve()
    data_dir = Path(args.data_dir).expanduser().resolve()
    test_dir = Path(args.test_dir).expanduser().resolve()

    model, meta = load_model(model_path, device)
    threshold = float(meta.get("threshold", 0.5))

    print("\n" + "#" * 72)
    print("# CNN INFERENCE DIAGNOSTICS")
    print("#" * 72)
    print(f"Device: {device}")
    print(f"Model: {model_path}")
    for k in ("best_val_auc", "threshold", "label_real", "label_fake", "architecture"):
        if k in meta:
            print(f"  checkpoint[{k}]: {meta[k]}")
    print(f"face_crop={args.face_crop}  skip_no_face={args.skip_no_face}  "
          f"resize_if_not_380={args.resize_if_not_380}  invert_output={args.invert_output}")
    print(f"Threshold: {threshold}")

    print("\n--- LABEL CONVENTION (train_deepfake_detection.py) ---")
    print("  collect_paths:  real/ -> 0.0,  fake/ -> 1.0")
    print("  FocalLossSigmoid + validate_batched: score = sigmoid(logit) = P(fake)")
    print("  pred fake if prob_fake >= threshold else real")
    print("  Conclusion: label direction is NOT reversed in training.")

    transform = get_transform()
    rng = random.Random(args.seed)

    groups: List[Tuple[str, List[Path], List[int]]] = []

    # Val-aligned samples (same split as training)
    val_paths, val_labels = sample_val_aligned_paths(
        data_dir, DIAGNOSE_N_PER_GROUP, DIAGNOSE_N_PER_GROUP, VAL_SPLIT_SEED
    )
    val_real = [(p, y) for p, y in zip(val_paths, val_labels) if y == 0]
    val_fake = [(p, y) for p, y in zip(val_paths, val_labels) if y == 1]
    groups.append(
        (
            f"final_dataset_aligned VAL real (n={len(val_real)}) — 380x380 pre-aligned",
            [p for p, _ in val_real],
            [y for _, y in val_real],
        )
    )
    groups.append(
        (
            f"final_dataset_aligned VAL fake (n={len(val_fake)}) — 380x380 pre-aligned",
            [p for p, _ in val_fake],
            [y for _, y in val_fake],
        )
    )

    test_real_dir = test_dir / "real"
    test_fake_dir = test_dir / "fake"
    test_real = sample_paths_from_dir(test_real_dir, DIAGNOSE_N_PER_GROUP, rng)
    test_fake = sample_paths_from_dir(test_fake_dir, DIAGNOSE_N_PER_GROUP, rng)
    groups.append(
        (f"test_images/real (n={len(test_real)})", test_real, [0] * len(test_real))
    )
    groups.append(
        (f"test_images/fake (n={len(test_fake)})", test_fake, [1] * len(test_fake))
    )

    all_results: Dict[str, List[InferenceResult]] = {}
    preprocess_notes: List[str] = []

    for group_name, paths, y_true in groups:
        inspect_image_sizes(paths, group_name.split("(")[0].strip())
        results: List[InferenceResult] = []
        for p in paths:
            pil_img = load_image_pil(p)
            prep = preprocess_image(
                pil_img,
                device=device,
                face_crop=args.face_crop,
                skip_no_face=args.skip_no_face,
                resize_if_not_380=args.resize_if_not_380,
            )
            if prep is None:
                print(f"  [skip] no face: {p.name}")
                continue
            if args.save_preprocessed:
                rel = p.stem + ".jpg"
                if "test_images" in group_name:
                    sub = "test_real" if y_true and y_true[0] == 0 else "test_fake"
                elif "VAL real" in group_name:
                    sub = "val_real"
                elif "VAL fake" in group_name:
                    sub = "val_fake"
                else:
                    sub = "other"
                out_p = Path(args.save_preprocessed) / sub / rel
                save_preprocessed_image(prep.image_np, out_p)

            logit = predict_logit(model, device, prep.image_np, transform)
            prob_fake = logit_to_fake_prob(logit, invert_output=args.invert_output)
            pred_fake = prob_to_pred(prob_fake, threshold)
            results.append(
                InferenceResult(
                    path=p,
                    logit=logit,
                    prob_fake=prob_fake,
                    pred_fake=pred_fake,
                    pred_label="fake" if pred_fake == 1 else "real",
                    face_detected=prep.face_detected,
                )
            )
            if prep.source_size != prep.output_size or prep.output_size != (380, 380):
                preprocess_notes.append(
                    f"{p.name}: src={prep.source_size} -> out={prep.output_size}"
                )

        all_results[group_name] = results
        print_group_diagnosis(
            group_name,
            paths,
            y_true[: len(results)],
            results,
            invert_output=args.invert_output,
            threshold=threshold,
        )

    # Compare val replay vs training export if available
    val_scores_path = model_path.parent / "val_scores.npz"
    if val_scores_path.is_file() and val_paths:
        print(f"\n--- Val scores file check: {val_scores_path} ---")
        try:
            _fft_dir = Path(__file__).resolve().parent / "fft"
            if _fft_dir.is_dir() and str(_fft_dir) not in sys.path:
                sys.path.insert(0, str(_fft_dir))
            npz = np.load(val_scores_path, allow_pickle=True)
            logits_npz = np.asarray(npz["logits"], dtype=np.float32)
            labels_npz = np.asarray(npz["labels"], dtype=np.float32)
            from fusion_scores import path_to_sample_id

            id_to_logit = {}
            id_key = "sample_ids" if "sample_ids" in npz else "sample_id"
            if id_key in npz:
                ids = npz[id_key]
                for sid, lg in zip(ids, logits_npz):
                    id_to_logit[str(sid)] = float(lg)
            matched = 0
            logit_diffs = []
            for p in val_paths[:5]:
                sid = path_to_sample_id(p, data_dir)
                if sid in id_to_logit:
                    our = predict_logit(
                        model,
                        device,
                        preprocess_image(
                            load_image_pil(p),
                            device=device,
                            face_crop=False,
                            skip_no_face=False,
                            resize_if_not_380=False,
                        ).image_np,
                        transform,
                    )
                    diff = abs(our - id_to_logit[sid])
                    logit_diffs.append(diff)
                    matched += 1
                    print(f"  {p.name}: export_logit={id_to_logit[sid]:+.4f} test_cnn_logit={our:+.4f} diff={diff:.6f}")
            if logit_diffs:
                print(f"  Mean |logit diff| on {matched} samples: {np.mean(logit_diffs):.6f}")
                if max(logit_diffs) < 1e-3:
                    print("  Conclusion: test_cnn matches export_spatial_scores / val dataloader.")
                else:
                    print("  WARNING: logit mismatch vs val_scores.npz — check model or preprocessing.")
        except ImportError:
            print("  (fusion_scores not importable; skip npz comparison)")

    # Domain / preprocessing conclusions
    print("\n" + "=" * 72)
    print("DIAGNOSTIC CONCLUSIONS")
    print("=" * 72)

    def _group_acc(key_substr: str, label_fake: bool) -> Optional[float]:
        for k, res in all_results.items():
            if key_substr in k and res:
                yt = 1 if label_fake else 0
                pr = [r.pred_fake for r in res]
                return float(np.mean(np.array([yt] * len(res)) == np.array(pr)))
        return None

    val_real_acc = _group_acc("VAL real", label_fake=False)
    val_fake_acc = _group_acc("VAL fake", label_fake=True)
    test_real_acc = _group_acc("test_images/real", label_fake=False)
    test_fake_acc = _group_acc("test_images/fake", label_fake=True)

    if val_real_acc is not None and val_fake_acc is not None:
        print(f"\n1. Model + val preprocessing on aligned 380x380 crops:")
        print(f"   VAL real accuracy: {val_real_acc:.2f}  |  VAL fake accuracy: {val_fake_acc:.2f}")
        if val_real_acc > 0.7 and val_fake_acc > 0.7:
            print("   -> Model loads correctly; inference matches training validation.")
        else:
            print("   -> WARNING: Poor val accuracy — model load or preprocessing bug.")

    if test_fake_acc is not None:
        test_fake_mean = np.mean([r.prob_fake for r in all_results.get(
            next(k for k in all_results if "test_images/fake" in k), []
        )]) if any("test_images/fake" in k for k in all_results) else float("nan")
        print(f"\n2. test_images/fake: mean fake_prob={test_fake_mean:.4f}, accuracy={test_fake_acc:.2f}")
        if test_fake_acc < 0.5 and test_fake_mean < 0.3:
            print("   -> Fakes scored as REAL (low P(fake)). NOT fixed by --invert_output alone")
            print("      if VAL fake accuracy is high (labels are correct).")

    if test_real_dir.is_dir() and test_fake_dir.is_dir():
        tr = sample_paths_from_dir(test_real_dir, 3, rng)
        tf = sample_paths_from_dir(test_fake_dir, 3, rng)
        print("\n3. Domain / preprocessing mismatch:")
        print("   Training data: 380x380 MTCNN-aligned face crops (face-swap deepfakes + real faces).")
        if tr:
            with Image.open(tr[0]) as im:
                print(f"   test_images/real example size: {im.size} (full frame, not pre-aligned).")
        if tf:
            with Image.open(tf[0]) as im:
                print(f"   test_images/fake example size: {im.size} (likely AI portrait, not face-swap crop).")
        if not args.face_crop:
            print("   -> Without --face_crop, non-380 images go to CNN at wrong scale/content.")
            print("      Use --face_crop for test_images, or pre-align to 380x380 like the training set.")
        else:
            print("   -> With --face_crop, faces are aligned to 380x380 but GENERATION DOMAIN may still differ")
            print("      (e.g. full-frame GAN portraits vs face-swap artifacts the model learned).")

    test_fake_inv_acc = None
    test_real_inv_acc = None
    val_inv_worse = False
    if val_fake_acc is not None and val_fake_acc > 0.8:
        val_inv_worse = True
    for k, res in all_results.items():
        if not res or "test_images" not in k:
            continue
        yt = [0] * len(res) if "real" in k else [1] * len(res)
        pr = [r.pred_fake for r in res]
        acc = float(np.mean(np.array(yt) == np.array(pr)))
        inv_acc = float(np.mean(np.array(yt) == (1 - np.array(pr))))
        if "fake" in k:
            test_fake_inv_acc = inv_acc
        else:
            test_real_inv_acc = inv_acc

    print("\n4. Label inversion hypothesis (--invert_output):")
    print("   Training: real=0, fake=1, sigmoid(logit)=P(fake). Checkpoint agrees.")
    if val_real_acc is not None and val_fake_acc is not None:
        print(
            f"   On VAL aligned crops: normal acc real={val_real_acc:.2f} fake={val_fake_acc:.2f}; "
            f"inverted would destroy both."
        )
    if test_fake_acc is not None and test_fake_inv_acc is not None:
        print(
            f"   On test_images/fake only: normal acc={test_fake_acc:.2f}, "
            f"inverted acc={test_fake_inv_acc:.2f}."
        )
    if val_inv_worse and test_fake_acc is not None and test_fake_acc < 0.2 and test_fake_inv_acc > 0.9:
        print(
            "   -> Do NOT use --invert_output globally. Labels are correct; test fakes get LOW P(fake)"
        )
        print(
            "      because they look like REAL faces to this model (domain shift), not because"
        )
        print("      sigmoid direction is reversed in the checkpoint.")
    elif test_fake_inv_acc is not None and test_fake_inv_acc > (test_fake_acc or 0) + 0.15:
        print("   -> Inversion helps test fakes only; still inconsistent with VAL — check test folder labels.")
    else:
        print("   -> Inversion does not reconcile VAL + test; root cause is domain/preprocessing.")

    if args.save_preprocessed:
        print(f"\n5. Saved preprocessed tensors to: {Path(args.save_preprocessed).resolve()}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="EfficientNet-B4 binary inference")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--image", type=str, help="Path to a single image file")
    mode.add_argument("--input_dir", type=str, help="Directory containing images")
    mode.add_argument(
        "--diagnose",
        action="store_true",
        help="Run diagnostic inference on aligned val + test_images samples",
    )

    parser.add_argument("--model_path", type=str, default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--data_dir", type=str, default=str(DEFAULT_ALIGNED_DIR))
    parser.add_argument("--test_dir", type=str, default=str(DEFAULT_TEST_DIR))
    parser.add_argument("--seed", type=int, default=0, help="RNG seed for diagnose sampling")
    parser.add_argument("--debug", action="store_true", help="Show tensor stats")
    parser.add_argument("--csv", action="store_true", help="Output in CSV format")
    parser.add_argument("--face_crop", action="store_true", help="MTCNN detect + 380x380 align")
    parser.add_argument("--skip_no_face", action="store_true", help="Skip images with no detected face")
    parser.add_argument(
        "--resize_if_not_380",
        action="store_true",
        default=True,
        help="When not using face_crop, bilinear resize non-380 inputs to 380 (default: on)",
    )
    parser.add_argument(
        "--no_resize_if_not_380",
        action="store_false",
        dest="resize_if_not_380",
        help="Do not resize; pass native resolution (not recommended for test_images)",
    )
    parser.add_argument(
        "--invert_output",
        action="store_true",
        help="Use P(real)=1-sigmoid(logit) instead of P(fake); for label-direction tests",
    )
    parser.add_argument(
        "--save_preprocessed",
        type=str,
        default=None,
        metavar="DIR",
        help="Save uint8 RGB tensors after crop/resize (before Normalize)",
    )
    args = parser.parse_args()

    if args.diagnose:
        return run_diagnose(args)

    if args.image:
        img_paths = [Path(args.image).expanduser().resolve()]
    else:
        img_paths = iter_image_paths(Path(args.input_dir).expanduser().resolve())
        if not img_paths:
            print("[!] No supported image files found in the directory.", file=sys.stderr)
            return 1

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = Path(args.model_path).expanduser().resolve()
    try:
        model, meta = load_model(model_path, device)
    except FileNotFoundError as e:
        print(f"[!] {e}", file=sys.stderr)
        return 1

    threshold = float(meta.get("threshold", 0.5))
    for meta_key in ("best_val_auc", "threshold", "label_real", "label_fake"):
        if meta_key in meta:
            print(f"[+] checkpoint {meta_key}: {meta[meta_key]}")

    transform = get_transform()
    y_true: List[int] = []
    y_pred: List[int] = []
    save_root = Path(args.save_preprocessed) if args.save_preprocessed else None

    if args.csv:
        print("filename,logit,probability_fake,predicted_label")

    for p in img_paths:
        try:
            pil_img = load_image_pil(p)
            prep = preprocess_image(
                pil_img,
                device=device,
                face_crop=args.face_crop,
                skip_no_face=args.skip_no_face,
                resize_if_not_380=args.resize_if_not_380,
            )
            if prep is None:
                print(f"[!] No face detected in {p.name}; skipped.", file=sys.stderr)
                continue

            if save_root is not None:
                rel = p.name
                if label_from_path(p) == 1:
                    sub = "fake"
                elif label_from_path(p) == 0:
                    sub = "real"
                else:
                    sub = "unknown"
                save_preprocessed_image(prep.image_np, save_root / sub / rel)

            logit = predict_logit(model, device, prep.image_np, transform, debug=args.debug)
            prob_fake = logit_to_fake_prob(logit, invert_output=args.invert_output)
            pred_fake = prob_to_pred(prob_fake, threshold)
            label = "fake" if pred_fake == 1 else "real"
            confidence = prob_fake if pred_fake == 1 else 1.0 - prob_fake

            if args.csv:
                print(f"{p.name},{logit:.6f},{prob_fake:.6f},{label}")
            else:
                face_note = ""
                if prep.face_detected is False:
                    face_note = " [no_face,fallback_resize]"
                elif prep.face_detected is True:
                    face_note = " [face_aligned]"
                print(
                    f"{p.name} | {label.upper()} | fake_prob={prob_fake:.3f} | "
                    f"confidence={confidence:.3f}{face_note}"
                )

            gt = label_from_path(p)
            if gt is not None and args.input_dir:
                y_true.append(gt)
                y_pred.append(pred_fake)

        except Exception as e:
            print(f"[!] Error processing {p}: {e}", file=sys.stderr)

    if args.input_dir and y_true:
        print_confusion_summary(y_true, y_pred, "=== CNN Test Summary ===")
        if args.invert_output:
            print("  (Note: --invert_output is active; metrics use inverted probabilities.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
