#!/usr/bin/env python3
"""
Manual Real Images Cleaner

Safely processes and copies valid images from images_real_manual_collected 
to final_dataset/real/manual with size and grayscale filtering.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Tuple
from PIL import Image
from tqdm import tqdm

# ============ CONFIGURABLE VARIABLES ============
INPUT_PATH = Path("images_real_manual_collected")  # Source directory
OUTPUT_PATH = Path("final_dataset/real/manual")  # Target directory
MIN_WIDTH = 128  # Minimum image width
MIN_HEIGHT = 128  # Minimum image height
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}  # Supported image formats
# =================================================

def is_valid_image_with_filters(image_path: Path) -> Tuple[bool, str]:
    """
    Check if image file is valid and meets all filtering criteria.
    Returns (is_valid, reason_for_skip)
    """
    try:
        with Image.open(image_path) as img:
            # Convert to RGB to check for grayscale
            rgb_img = img.convert('RGB')
            
            # Check if original was grayscale
            if img.mode == 'L' or (img.mode == 'P' and len(img.getcolors()) <= 256):
                return False, "grayscale image"
            
            # Check image dimensions
            width, height = rgb_img.size
            if width < MIN_WIDTH or height < MIN_HEIGHT:
                return False, f"small size ({width}x{height})"
            
            # Verify image is not corrupted
            rgb_img.verify()
            
        return True, ""
        
    except Exception as e:
        return False, f"corrupted/unreadable: {str(e)[:50]}"

def discover_images(input_dir: Path) -> list:
    """Discover all image files in the input directory."""
    print(f"Scanning {input_dir} for images...")
    
    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist!")
        return []
    
    image_files = []
    
    # Find all files with supported extensions
    for ext in SUPPORTED_EXTENSIONS:
        pattern = f"**/*{ext}"
        found_files = list(input_dir.glob(pattern))
        image_files.extend(found_files)
    
    return image_files

def get_unique_filename(output_path: Path, original_name: str) -> str:
    """Generate unique filename to avoid conflicts."""
    if not (output_path / original_name).exists():
        return original_name
    
    # Add UUID suffix to avoid conflicts
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    unique_id = str(uuid.uuid4())[:8]
    return f"{stem}_{unique_id}{suffix}"

def ensure_output_directory(output_path: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_path.mkdir(parents=True, exist_ok=True)

def copy_images_safely(image_files: list, output_path: Path) -> Tuple[int, int]:
    """
    Process and copy images safely with filtering.
    Returns (copied_count, skipped_count)
    """
    copied_count = 0
    skipped_count = 0
    skip_reasons = {}
    
    for img_path in tqdm(image_files, desc="Processing images"):
        is_valid, skip_reason = is_valid_image_with_filters(img_path)
        
        if is_valid:
            try:
                # Generate unique filename if needed
                unique_filename = get_unique_filename(output_path, img_path.name)
                dest_path = output_path / unique_filename
                
                # Copy file preserving metadata
                shutil.copy2(img_path, dest_path)
                copied_count += 1
                
            except Exception as e:
                print(f"Warning: Failed to copy {img_path}: {e}")
                skipped_count += 1
                skip_reasons['copy_error'] = skip_reasons.get('copy_error', 0) + 1
        else:
            skipped_count += 1
            skip_reasons[skip_reason] = skip_reasons.get(skip_reason, 0) + 1
    
    # Print skip reasons summary
    if skip_reasons:
        print("\nSkip reasons:")
        for reason, count in skip_reasons.items():
            print(f"  {reason}: {count}")
    
    return copied_count, skipped_count

def main():
    """Main function to clean and copy manual real images."""
    print("=== Manual Real Images Cleaner ===")
    print(f"Input path: {INPUT_PATH}")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Minimum size: {MIN_WIDTH}x{MIN_HEIGHT}")
    print()
    
    # Discover all images
    image_files = discover_images(INPUT_PATH)
    total_scanned = len(image_files)
    
    if total_scanned == 0:
        print("No images found in the input directory!")
        return
    
    print(f"Total images found: {total_scanned}")
    print()
    
    # Ensure output directory exists
    ensure_output_directory(OUTPUT_PATH)
    
    # Process and copy images
    copied_count, skipped_count = copy_images_safely(image_files, OUTPUT_PATH)
    
    print()
    print("=== Summary ===")
    print(f"Total images scanned: {total_scanned}")
    print(f"Valid images copied: {copied_count}")
    print(f"Images skipped: {skipped_count}")
    print(f"Output directory: {OUTPUT_PATH}")
    print("Done!")

if __name__ == "__main__":
    main()


