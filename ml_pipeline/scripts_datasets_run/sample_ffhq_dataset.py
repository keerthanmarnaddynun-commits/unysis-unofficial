#!/usr/bin/env python3
"""
FFHQ Dataset Random Sampler

Safely samples 10,000 random images from FFHQ dataset and copies them to a structured output directory.
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
FFHQ_PATH = Path("FFHQ")  # Path to FFHQ dataset root
OUTPUT_PATH = Path("final_dataset/real/ffhq")  # Output directory
SAMPLE_SIZE = 10000  # Number of images to sample
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

def discover_images(root_path: Path) -> List[Path]:
    """Recursively discover all valid image files in the dataset."""
    print(f"Scanning {root_path} for images...")
    image_files = []
    
    for ext in SUPPORTED_EXTENSIONS:
        pattern = f"**/*{ext}"
        found_files = list(root_path.glob(pattern))
        image_files.extend(found_files)
    
    # Filter out directories and validate images
    valid_images = []
    for img_path in tqdm(image_files, desc="Validating images"):
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

def copy_images_safely(selected_images: List[Path], output_path: Path) -> int:
    """Safely copy images to output directory with progress tracking."""
    copied_count = 0
    
    for img_path in tqdm(selected_images, desc="Copying images"):
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

def main():
    """Main function to sample and copy FFHQ images."""
    print("=== FFHQ Dataset Random Sampler ===")
    print(f"Input path: {FFHQ_PATH}")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Sample size: {SAMPLE_SIZE}")
    print(f"Random seed: {RANDOM_SEED}")
    print()
    
    # Validate input directory exists
    if not FFHQ_PATH.exists():
        print(f"Error: Input directory {FFHQ_PATH} does not exist!")
        return
    
    # Set random seed for reproducibility
    random.seed(RANDOM_SEED)
    
    # Discover all valid images
    all_images = discover_images(FFHQ_PATH)
    total_found = len(all_images)
    print(f"Total valid images found: {total_found}")
    
    if total_found == 0:
        print("No valid images found in the dataset!")
        return
    
    # Sample images
    if total_found <= SAMPLE_SIZE:
        print(f"Found {total_found} images (≤ {SAMPLE_SIZE}), copying all...")
        selected_images = all_images
    else:
        print(f"Randomly sampling {SAMPLE_SIZE} images from {total_found}...")
        selected_images = random.sample(all_images, SAMPLE_SIZE)
    
    # Ensure output directory exists
    ensure_output_directory(OUTPUT_PATH)
    
    # Copy images safely
    copied_count = copy_images_safely(selected_images, OUTPUT_PATH)
    
    print()
    print("=== Summary ===")
    print(f"Total images found: {total_found}")
    print(f"Images selected: {len(selected_images)}")
    print(f"Images successfully copied: {copied_count}")
    print(f"Output directory: {OUTPUT_PATH}")
    print("Done!")

if __name__ == "__main__":
    main()
