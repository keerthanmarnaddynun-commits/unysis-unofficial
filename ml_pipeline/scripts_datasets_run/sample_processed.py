#!/usr/bin/env python3
"""
Processed Dataset Random Sampler

Safely samples 5,000 real and 5,000 fake images from processed_data/final dataset 
and copies them to structured final_dataset directories.
"""

import os
import shutil
import uuid
import random
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from tqdm import tqdm

# ============ CONFIGURABLE VARIABLES ============
PROCESSED_DATA_PATH = Path("ml_pipeline/processed_data/final/train")  # Path to processed dataset
OUTPUT_PATH = Path("final_dataset")  # Base output directory
REAL_SAMPLE_SIZE = 5000  # Number of real images to sample
FAKE_SAMPLE_SIZE = 5000  # Number of fake images to sample
RANDOM_SEED = 42  # Fixed seed for reproducibility
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}  # Supported image formats
# =================================================

def is_valid_image(image_path: Path) -> bool:
    """Check if image file is valid using PIL."""
    try:
        with Image.open(image_path) as img:
            img.verify()
        return True
    except Exception:
        return False

def discover_images(input_dir: Path, category: str) -> List[Path]:
    """Recursively discover all valid image files in the specified category directory."""
    category_dir = input_dir / category
    print(f"Scanning {category_dir} for {category} images...")
    
    if not category_dir.exists():
        print(f"Warning: {category_dir} does not exist!")
        return []
    
    image_files = []
    
    # Find all files with supported extensions
    for ext in SUPPORTED_EXTENSIONS:
        pattern = f"**/*{ext}"
        found_files = list(category_dir.glob(pattern))
        image_files.extend(found_files)
    
    # Filter out directories and validate images
    valid_images = []
    for img_path in tqdm(image_files, desc=f"Validating {category} images"):
        if img_path.is_file() and is_valid_image(img_path):
            valid_images.append(img_path)
    
    return valid_images

def ensure_output_directory(output_path: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_path.mkdir(parents=True, exist_ok=True)

def get_unique_filename(output_path: Path, original_name: str) -> str:
    """Generate unique filename to avoid conflicts."""
    if not (output_path / original_name).exists():
        return original_name
    
    # Add UUID suffix to avoid conflicts
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    unique_id = str(uuid.uuid4())[:8]
    return f"{stem}_{unique_id}{suffix}"

def copy_images_safely(selected_images: List[Path], output_path: Path, category: str) -> int:
    """Safely copy images to output directory with progress tracking."""
    copied_count = 0
    
    for img_path in tqdm(selected_images, desc=f"Copying {category} images"):
        try:
            # Generate unique filename if needed
            unique_filename = get_unique_filename(output_path, img_path.name)
            dest_path = output_path / unique_filename
            
            # Copy file preserving metadata
            shutil.copy2(img_path, dest_path)
            copied_count += 1
            
        except Exception as e:
            print(f"Warning: Failed to copy {img_path}: {e}")
            continue
    
    return copied_count

def sample_images(images: List[Path], sample_size: int) -> List[Path]:
    """Sample images randomly with fixed seed."""
    if len(images) <= sample_size:
        print(f"Found {len(images)} images (≤ {sample_size}), copying all...")
        return images
    else:
        print(f"Randomly sampling {sample_size} images from {len(images)}...")
        return random.sample(images, sample_size)

def main():
    """Main function to sample and copy processed images."""
    print("=== Processed Dataset Random Sampler ===")
    print(f"Input path: {PROCESSED_DATA_PATH}")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Real sample size: {REAL_SAMPLE_SIZE}")
    print(f"Fake sample size: {FAKE_SAMPLE_SIZE}")
    print(f"Random seed: {RANDOM_SEED}")
    print()
    
    # Set random seed for reproducibility
    random.seed(RANDOM_SEED)
    
    # Discover real and fake images
    real_images = discover_images(PROCESSED_DATA_PATH, "real")
    fake_images = discover_images(PROCESSED_DATA_PATH, "fake")
    
    total_real_found = len(real_images)
    total_fake_found = len(fake_images)
    
    print(f"Total valid real images found: {total_real_found}")
    print(f"Total valid fake images found: {total_fake_found}")
    print()
    
    if total_real_found == 0 and total_fake_found == 0:
        print("No valid images found in the dataset!")
        return
    
    # Sample images
    selected_real = sample_images(real_images, REAL_SAMPLE_SIZE)
    selected_fake = sample_images(fake_images, FAKE_SAMPLE_SIZE)
    
    # Ensure output directories exist
    real_output_path = OUTPUT_PATH / "real" / "processed"
    fake_output_path = OUTPUT_PATH / "fake" / "processed"
    
    ensure_output_directory(real_output_path)
    ensure_output_directory(fake_output_path)
    
    # Copy images safely
    real_copied = 0
    fake_copied = 0
    
    if selected_real:
        real_copied = copy_images_safely(selected_real, real_output_path, "real")
    
    if selected_fake:
        fake_copied = copy_images_safely(selected_fake, fake_output_path, "fake")
    
    print()
    print("=== Summary ===")
    print(f"Real images found: {total_real_found}")
    print(f"Real images selected: {len(selected_real)}")
    print(f"Real images successfully copied: {real_copied}")
    print()
    print(f"Fake images found: {total_fake_found}")
    print(f"Fake images selected: {len(selected_fake)}")
    print(f"Fake images successfully copied: {fake_copied}")
    print()
    print(f"Total images copied: {real_copied + fake_copied}")
    print(f"Real output directory: {real_output_path}")
    print(f"Fake output directory: {fake_output_path}")
    print("Done!")

if __name__ == "__main__":
    main()
