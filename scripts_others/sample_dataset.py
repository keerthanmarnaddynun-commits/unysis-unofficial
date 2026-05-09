"""
sample_dataset.py
-----------------
Randomly samples images from FFHQ and StyleGAN "Fake faces" folders,
then copies them into a structured final_dataset directory.

Existing subfolders (processed/, collected/) are never touched.
"""

import os
import random
import shutil
import uuid
from pathlib import Path

from tqdm import tqdm

# ─────────────────────────────────────────────
#  CONFIGURATION  ← edit these paths as needed
# ─────────────────────────────────────────────
FFHQ_PATH          = r"D:\datasets\ffhq"                     # FFHQ root (real images)
STYLEGAN_FAKE_PATH = r"D:\datasets\stylegan\Fake faces"      # StyleGAN fake subfolder

OUTPUT_REAL_FFHQ   = r"D:\forsen\final_dataset\real\ffhq"
OUTPUT_FAKE_GAN    = r"D:\forsen\final_dataset\fake\gan"

SAMPLE_SIZE        = 10_000   # target images per source
RANDOM_SEED        = 42       # fixed seed for reproducibility

# Extensions considered valid image files (case-insensitive)
IMAGE_EXTENSIONS   = {".jpg", ".jpeg", ".png", ".webp"}

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def collect_images(folder: str) -> list[Path]:
    """
    Recursively collect all image files under *folder*.
    Returns a sorted list of Path objects for reproducibility.
    """
    folder_path = Path(folder)
    if not folder_path.exists():
        raise FileNotFoundError(f"Source folder not found: {folder}")

    images = [
        p for p in folder_path.rglob("*")
        if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    ]
    images.sort()          # deterministic order before sampling
    return images


def sample_images(images: list[Path], n: int, seed: int) -> list[Path]:
    """
    Randomly sample *n* images from *images* using *seed*.
    If len(images) < n, returns all images (with a warning).
    """
    rng = random.Random(seed)
    if len(images) <= n:
        print(f"  ⚠  Only {len(images):,} images found (< {n:,}). Copying all.")
        return images
    return rng.sample(images, n)


def resolve_dest_path(dest_dir: Path, src_path: Path, existing_names: set[str]) -> Path:
    """
    Return a collision-free destination path inside *dest_dir*.
    If the filename already exists in *existing_names*, append a short UUID suffix.
    """
    name  = src_path.name
    stem  = src_path.stem
    ext   = src_path.suffix.lower()

    while name in existing_names:
        name = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"

    existing_names.add(name)
    return dest_dir / name


def is_valid_image(path: Path) -> bool:
    """
    Quick sanity check: try opening the first few bytes to detect corruption.
    Requires Pillow. Falls back to True if Pillow is not installed.
    """
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.verify()          # cheap check, no full decode
        return True
    except ImportError:
        return True               # Pillow not available → skip check
    except Exception:
        return False


def copy_images(
    sampled: list[Path],
    dest_dir: Path,
    label: str,
) -> int:
    """
    Copy *sampled* images into *dest_dir*, skipping corrupted files and
    resolving filename conflicts with UUID suffixes.

    Returns the number of successfully copied images.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Build a set of names already present in the destination
    existing_names: set[str] = {p.name for p in dest_dir.iterdir() if p.is_file()}

    copied  = 0
    skipped = 0

    for src in tqdm(sampled, desc=f"  Copying → {label}", unit="img"):
        if not is_valid_image(src):
            skipped += 1
            continue

        dest = resolve_dest_path(dest_dir, src, existing_names)
        try:
            shutil.copy2(src, dest)
            copied += 1
        except OSError as exc:
            print(f"\n  ✗ Failed to copy {src.name}: {exc}")
            skipped += 1

    if skipped:
        print(f"  ⚠  Skipped {skipped:,} file(s) (corrupted or copy error).")

    return copied


# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Dataset Sampler")
    print("=" * 60)

    # ── 1. Collect images ──────────────────────────────────────
    print("\n[1/4] Scanning source folders …")

    print(f"  FFHQ        → {FFHQ_PATH}")
    ffhq_all = collect_images(FFHQ_PATH)
    print(f"         Found {len(ffhq_all):>8,} images")

    print(f"  StyleGAN    → {STYLEGAN_FAKE_PATH}")
    gan_all  = collect_images(STYLEGAN_FAKE_PATH)
    print(f"         Found {len(gan_all):>8,} images")

    # ── 2. Sample ──────────────────────────────────────────────
    print(f"\n[2/4] Sampling up to {SAMPLE_SIZE:,} images each (seed={RANDOM_SEED}) …")

    ffhq_sample = sample_images(ffhq_all, SAMPLE_SIZE, seed=RANDOM_SEED)
    gan_sample  = sample_images(gan_all,  SAMPLE_SIZE, seed=RANDOM_SEED + 1)  # different sub-seed

    print(f"  FFHQ sample : {len(ffhq_sample):,}")
    print(f"  GAN  sample : {len(gan_sample):,}")

    # ── 3. Copy ────────────────────────────────────────────────
    print("\n[3/4] Copying files …")

    ffhq_copied = copy_images(ffhq_sample, Path(OUTPUT_REAL_FFHQ), label="real/ffhq")
    gan_copied  = copy_images(gan_sample,  Path(OUTPUT_FAKE_GAN),  label="fake/gan")

    # ── 4. Summary ─────────────────────────────────────────────
    print("\n[4/4] Summary")
    print("=" * 60)
    print(f"  real/ffhq  : {ffhq_copied:,} images copied  →  {OUTPUT_REAL_FFHQ}")
    print(f"  fake/gan   : {gan_copied:,} images copied  →  {OUTPUT_FAKE_GAN}")
    print("=" * 60)
    print("Done. ✓")


if __name__ == "__main__":
    main()
