import json
import os
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


ROOT = Path("D:/forsen")
REPORT_PATH = ROOT / "tools" / "dataset_audit_report.json"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def infer_dataset_root() -> Path:
    preferred = ROOT / "dataset"
    fallback = ROOT / "base_deepfake"
    return preferred if preferred.is_dir() else fallback


def list_images(dir_path: Path):
    if not dir_path.exists():
        return []
    return [p for p in dir_path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]


def split_class_counts(dataset_root: Path):
    summary = {}
    for split in ("train", "val", "test"):
        split_counts = {}
        for cls in ("real", "fake"):
            files = list_images(dataset_root / split / cls)
            split_counts[cls] = len(files)
        if split_counts["real"] or split_counts["fake"]:
            summary[split] = split_counts
    return summary


def all_real_images(dataset_root: Path):
    items = []
    for split in ("train", "val", "test"):
        items.extend(list_images(dataset_root / split / "real"))
    return items


def identity_key(path: Path) -> str:
    stem = path.stem
    if "_frame_" in stem:
        return stem.split("_frame_")[0]
    if "_face_" in stem:
        return stem.split("_face_")[0]
    return stem


def dhash_pil(img: Image.Image, hash_size: int = 8) -> str:
    gray = img.convert("L").resize((hash_size + 1, hash_size))
    arr = np.asarray(gray, dtype=np.uint8)
    diff = arr[:, 1:] > arr[:, :-1]
    return "".join("1" if x else "0" for x in diff.flatten())


def image_metrics(paths):
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    hashes = Counter()
    lighting_means = []
    lighting_stds = []
    blur_scores = []
    size_bytes = []
    face_count = 0
    multi_face_count = 0
    no_face_count = 0

    for p in paths:
        try:
            img = Image.open(p).convert("RGB")
            hashes[dhash_pil(img)] += 1
            arr = np.asarray(img)
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)

            lighting_means.append(float(np.mean(gray)))
            lighting_stds.append(float(np.std(gray)))
            blur_scores.append(float(cv2.Laplacian(gray, cv2.CV_64F).var()))
            size_bytes.append(p.stat().st_size)

            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            if len(faces) == 0:
                no_face_count += 1
            else:
                face_count += 1
                if len(faces) > 1:
                    multi_face_count += 1
        except Exception:
            continue

    total = len(paths) if paths else 1
    duplicate_images = sum(c - 1 for c in hashes.values() if c > 1)
    dup_ratio = duplicate_images / total

    def stats(v):
        if not v:
            return {"min": None, "max": None, "mean": None, "std": None}
        a = np.asarray(v, dtype=float)
        return {
            "min": float(np.min(a)),
            "max": float(np.max(a)),
            "mean": float(np.mean(a)),
            "std": float(np.std(a)),
        }

    return {
        "near_duplicate_ratio_dhash": float(dup_ratio),
        "unique_hashes": int(len(hashes)),
        "lighting_mean_stats": stats(lighting_means),
        "lighting_std_stats": stats(lighting_stds),
        "blur_laplacian_var_stats": stats(blur_scores),
        "file_size_bytes_stats": stats(size_bytes),
        "faces_detected_count": int(face_count),
        "no_face_count": int(no_face_count),
        "multi_face_count": int(multi_face_count),
    }


def main():
    dataset_root = infer_dataset_root()
    counts = split_class_counts(dataset_root)
    real_imgs = all_real_images(dataset_root)
    fake_imgs = []
    for split in ("train", "val", "test"):
        fake_imgs.extend(list_images(dataset_root / split / "fake"))

    identity_counter = Counter(identity_key(p) for p in real_imgs)
    repeated_identity_count = sum(1 for _, c in identity_counter.items() if c > 1)
    top_repeated = identity_counter.most_common(20)

    report = {
        "dataset_root": str(dataset_root),
        "exists": dataset_root.exists(),
        "class_balance": counts,
        "total_real_images": len(real_imgs),
        "total_fake_images": len(fake_imgs),
        "real_identity_estimate": {
            "unique_identity_keys": len(identity_counter),
            "repeated_identity_keys": repeated_identity_count,
            "top_repeated_keys": top_repeated,
        },
        "real_image_metrics": image_metrics(real_imgs),
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
