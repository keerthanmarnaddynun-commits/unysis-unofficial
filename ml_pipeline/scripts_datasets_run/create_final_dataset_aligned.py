#!/usr/bin/env python3
"""
create_final_dataset_aligned.py

Goal: Build a high-quality, balanced, aligned dataset for deepfake detection.

Input structure:
  final_dataset/
    fake/
      gan/
      processed/
    real/
      ffhq/
      manual/
      multiface/
      processed/
      rir/
      teenage/

Output structure:
  final_dataset_aligned/
    real/
    fake/

Key rules implemented:
- Use ALL fake images (no sampling).
- Real images:
  - Keep ALL from small sources: manual, multiface, rir, teenage.
  - Sample the remaining required real images from (ffhq + processed) combined,
    shuffled and sampled with --seed.
- Face detection/alignment:
  - MTCNN (facenet-pytorch), landmarks=True
  - Select largest face
  - Expand detected box by 30% before alignment
  - Similarity transform using 5-point landmarks to canonical face
  - Output 380x380 RGB JPEG (quality=95)
- Multiprocessing with per-worker MTCNN init + tqdm progress bar
- Logs:
  - skipped_no_face.txt
  - skipped_error.txt
  (written under output_root)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import sys
import traceback
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFile
from tqdm import tqdm

ImageFile.LOAD_TRUNCATED_IMAGES = True

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png"}

# --------- Worker-global model (initialized per process) ---------
_MTCNN = None


def init_worker(device: str):
    """Initializer for each process: create MTCNN once per worker."""
    global _MTCNN
    from facenet_pytorch import MTCNN  # lazy import for Windows spawn safety

    _MTCNN = MTCNN(
        image_size=160,  # internal; we do our own warp to requested out_size
        margin=0,
        min_face_size=20,
        thresholds=[0.6, 0.7, 0.7],
        factor=0.709,
        post_process=False,
        device=device,
        keep_all=True,
    )


# --------- Required modular functions ---------

def load_image(path: Path) -> Optional[Image.Image]:
    """
    Load an image safely with PIL.
    Returns RGB image or None if corrupted/unreadable.
    """
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
        return im
    except Exception:
        return None


def detect_and_align_face(
    pil_rgb: Image.Image,
    out_size: int = 380,
    margin_frac: float = 0.30,
) -> Optional[Image.Image]:
    """
    Detect the largest face using MTCNN, align with a similarity transform using 5-point landmarks,
    and return an aligned PIL RGB face image (out_size x out_size). Returns None if no face.
    """
    global _MTCNN
    if _MTCNN is None:
        raise RuntimeError("MTCNN is not initialized. Ensure init_worker() runs in each process.")

    import cv2  # lazy import

    boxes, probs, landmarks = _MTCNN.detect(pil_rgb, landmarks=True)
    if boxes is None or landmarks is None or len(boxes) == 0:
        return None

    boxes = np.asarray(boxes, dtype=np.float32)
    landmarks = np.asarray(landmarks, dtype=np.float32)  # (N, 5, 2)

    # Select largest face by area
    areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
    idx = int(np.argmax(areas))
    box = boxes[idx]
    lm = landmarks[idx]

    img = np.asarray(pil_rgb, dtype=np.uint8)
    h, w = img.shape[:2]

    # Expand box by margin_frac (30%) before alignment
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

    # Landmarks relative to crop
    lm_crop = lm.copy()
    lm_crop[:, 0] -= float(nx1)
    lm_crop[:, 1] -= float(ny1)

    # Canonical 5-point template (ArcFace-style for 112x112), scaled to out_size
    # Order: left_eye, right_eye, nose, left_mouth, right_mouth
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

    aligned = cv2.warpAffine(
        crop,
        M,
        (out_size, out_size),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )

    return Image.fromarray(aligned, mode="RGB")


def process_image(
    item: "WorkItem",
    out_root: Path,
    out_size: int,
    quality: int,
    margin_frac: float,
) -> Tuple[str, str]:
    """
    Process one image end-to-end: load -> detect+align -> save.

    Returns:
      ("ok", output_path)
      ("no_face", input_path)
      ("error", "<input_path>\\n<traceback>") or ("error", input_path) for decode errors
    """
    try:
        im = load_image(item.path)
        if im is None:
            return ("error", str(item.path))

        aligned = detect_and_align_face(im, out_size=out_size, margin_frac=margin_frac)
        if aligned is None:
            return ("no_face", str(item.path))

        out_dir = out_root / item.label
        out_dir.mkdir(parents=True, exist_ok=True)

        out_path = out_dir / item.out_name
        aligned.save(out_path, format="JPEG", quality=quality, subsampling=0, optimize=True)
        return ("ok", str(out_path))
    except Exception:
        return ("error", f"{item.path}\n{traceback.format_exc()}")


# --------- Dataset selection (controlled sampling) ---------

@dataclass(frozen=True)
class WorkItem:
    path: Path
    label: str  # "real" or "fake"
    source: str  # e.g. ffhq, manual, gan, processed
    out_name: str


def iter_images(root: Path) -> List[Path]:
    paths: List[Path] = []
    if not root.exists():
        return paths
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            paths.append(p)
    return paths


def get_source_folder(path: Path, class_root: Path) -> str:
    """
    source folder is the first folder under class_root (real/ or fake/).
    Example: final_dataset/real/ffhq/xxx.jpg -> ffhq
    """
    rel = path.relative_to(class_root)
    parts = rel.parts
    if len(parts) == 0:
        return "unknown"
    return parts[0]


def make_out_name(source: str, path: Path, input_root: Path) -> str:
    """
    Format: <sourcefolder>_<originalname>_<uniqueid>.jpg
    uniqueid is a stable hash of the relative path to avoid collisions deterministically.
    """
    original = path.stem
    rel = str(path.relative_to(input_root)).replace("\\", "/").encode("utf-8", errors="ignore")
    uid = hashlib.sha1(rel).hexdigest()[:10]
    return f"{source}_{original}_{uid}.jpg"


def build_selected_items(input_root: Path, seed: int) -> Tuple[List[WorkItem], Dict[str, int]]:
    """
    Implements the controlled sampling rules and returns:
      - selected WorkItems (all fake + selected real)
      - real_counts_by_source (selected counts for each real source folder)
    """
    fake_root = input_root / "fake"
    real_root = input_root / "real"

    # STEP 1: Collect ALL fake images (no sampling)
    fake_paths = iter_images(fake_root)
    n_fake = len(fake_paths)

    # Real: small sources kept fully
    small_sources = ["manual", "multiface", "rir", "teenage"]
    large_sources = ["ffhq", "processed"]

    small_real_paths: List[Path] = []
    per_small_counts: Dict[str, int] = {}
    for src in small_sources:
        src_paths = iter_images(real_root / src)
        per_small_counts[src] = len(src_paths)
        small_real_paths.extend(src_paths)

    small_real_count = len(small_real_paths)

    # STEP 4: Remaining required real images
    remaining_real = n_fake - small_real_count
    if remaining_real < 0:
        raise RuntimeError(
            "Cannot satisfy balance constraints:\n"
            f"- fake images (use all): {n_fake}\n"
            f"- real images in small sources (must keep all): {small_real_count}\n"
            "Small real sources already exceed the number of fake images.\n"
            "Add more fake images or revise the constraints."
        )

    # STEP 5: Sample remaining_real from ffhq + processed combined
    large_pool: List[Path] = []
    per_large_available: Dict[str, int] = {}
    for src in large_sources:
        src_paths = iter_images(real_root / src)
        per_large_available[src] = len(src_paths)
        large_pool.extend(src_paths)

    if remaining_real > len(large_pool):
        raise RuntimeError(
            "Cannot satisfy balance constraints:\n"
            f"- fake images (use all): {n_fake}\n"
            f"- small real kept: {small_real_count}\n"
            f"- remaining_real needed from (ffhq+processed): {remaining_real}\n"
            f"- available in (ffhq+processed): {len(large_pool)} (ffhq={per_large_available['ffhq']}, processed={per_large_available['processed']})\n"
            "Not enough real images in large sources to reach balance."
        )

    rng = random.Random(seed)
    rng.shuffle(large_pool)  # important: mix both folders before sampling
    sampled_large = large_pool[:remaining_real]

    selected_real = small_real_paths + sampled_large

    # Build WorkItems
    items: List[WorkItem] = []

    for p in fake_paths:
        src = get_source_folder(p, fake_root)
        items.append(
            WorkItem(
                path=p,
                label="fake",
                source=src,
                out_name=make_out_name(src, p, input_root),
            )
        )

    for p in selected_real:
        src = get_source_folder(p, real_root)
        items.append(
            WorkItem(
                path=p,
                label="real",
                source=src,
                out_name=make_out_name(src, p, input_root),
            )
        )

    real_counts = Counter([wi.source for wi in items if wi.label == "real"])
    return items, dict(real_counts)


def main():
    parser = argparse.ArgumentParser(description="Create final balanced aligned dataset (MTCNN + 5pt alignment).")
    parser.add_argument("--input_root", type=str, default="final_dataset", help="Input dataset root folder")
    parser.add_argument("--output_root", type=str, default="final_dataset_aligned", help="Output dataset root folder")
    parser.add_argument("--out_size", type=int, default=380, help="Output aligned face size (square)")
    parser.add_argument("--quality", type=int, default=95, help="JPEG quality")
    parser.add_argument("--margin", type=float, default=0.30, help="Margin fraction around detected face box")
    parser.add_argument("--seed", type=int, default=1337, help="Random seed for controlled sampling")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1), help="Number of processes")
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help='Torch device for MTCNN, e.g. "cpu" or "cuda:0"',
    )
    args = parser.parse_args()

    input_root = Path(args.input_root).resolve()
    out_root = Path(args.output_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    try:
        items, real_counts_by_source = build_selected_items(input_root, seed=args.seed)
    except Exception as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)

    n_fake = sum(1 for x in items if x.label == "fake")
    n_real = sum(1 for x in items if x.label == "real")

    if n_fake != n_real:
        print(
            f"Internal selection error: dataset is not balanced (fake={n_fake}, real={n_real})",
            file=sys.stderr,
        )
        sys.exit(2)

    # Print selection summary (before alignment)
    print("Selection summary (before alignment):")
    print(f"- fake used (all): {n_fake}")
    print(f"- real used (controlled): {n_real}")
    print("- real counts by subfolder:")
    for k in sorted(real_counts_by_source.keys()):
        print(f"  - {k}: {real_counts_by_source[k]}")

    # Multiprocessing alignment
    skipped_no_face: List[str] = []
    skipped_error: List[str] = []
    ok_by_label = Counter()
    skipped_by_label_no_face = Counter()
    skipped_by_label_error = Counter()
    ok_real_by_source = Counter()

    from concurrent.futures import ProcessPoolExecutor, as_completed

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=init_worker,
        initargs=(args.device,),
    ) as ex:
        future_to_item = {
            ex.submit(
                process_image,
                item,
                out_root,
                args.out_size,
                args.quality,
                args.margin,
            ): item
            for item in items
        }

        for fut in tqdm(as_completed(future_to_item), total=len(future_to_item), desc="Aligning faces"):
            item = future_to_item[fut]
            status, info = fut.result()
            if status == "ok":
                ok_by_label[item.label] += 1
                if item.label == "real":
                    ok_real_by_source[item.source] += 1
            elif status == "no_face":
                skipped_no_face.append(info)
                skipped_by_label_no_face[item.label] += 1
            else:
                skipped_error.append(info)
                skipped_by_label_error[item.label] += 1

    # Write logs
    (out_root / "skipped_no_face.txt").write_text("\n".join(skipped_no_face), encoding="utf-8")
    (out_root / "skipped_error.txt").write_text("\n\n".join(skipped_error), encoding="utf-8")

    # Final output log
    print("\nFinal processing summary:")
    print(f"- total fake images selected: {n_fake}")
    print(f"- total real images selected: {n_real}")
    print("- saved:")
    print(f"  - fake: {ok_by_label['fake']}")
    print(f"  - real: {ok_by_label['real']}")
    print("- skipped (no face):")
    print(f"  - fake: {skipped_by_label_no_face['fake']}")
    print(f"  - real: {skipped_by_label_no_face['real']}")
    print("- skipped (error/corrupt):")
    print(f"  - fake: {skipped_by_label_error['fake']}")
    print(f"  - real: {skipped_by_label_error['real']}")

    print("- real saved counts by subfolder:")
    for k in sorted(real_counts_by_source.keys()):
        print(f"  - {k}: {ok_real_by_source.get(k, 0)} / selected {real_counts_by_source[k]}")

    print(f"\nOutput folder: {out_root}")
    print(f"Logs: {out_root / 'skipped_no_face.txt'} and {out_root / 'skipped_error.txt'}")


if __name__ == "__main__":
    # On Windows, multiprocessing requires this guard.
    main()

