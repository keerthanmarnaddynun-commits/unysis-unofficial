#!/usr/bin/env python3
"""
Teenage Faces Cleaner

Filters and extracts high-quality teenage face images from run2/teenage dataset 
using OpenCV face detection, quality filters, and 50% random sampling.
"""

import os
import shutil
import uuid
import cv2
import numpy as np
import random
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from tqdm import tqdm

# ============ CONFIGURABLE VARIABLES ============
INPUT_PATH = Path("run2/teenage")  # Source directory
OUTPUT_PATH = Path("final_dataset/real/teenage")  # Target directory
MIN_FACE_WIDTH = 100  # Minimum face width in pixels
MIN_FACE_HEIGHT = 100  # Minimum face height in pixels
BLUR_THRESHOLD = 120  # Variance of Laplacian threshold (lower = blurrier)
MIN_BRIGHTNESS = 50  # Minimum mean brightness
MAX_BRIGHTNESS = 210  # Maximum mean brightness
SAMPLING_RATIO = 0.5  # Keep 50% of filtered images
RANDOM_SEED = 42  # Fixed seed for reproducible sampling
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}  # Supported image formats
HAAR_CASCADE_PATH = 'haarcascade_frontalface_default.xml'  # OpenCV Haar Cascade
# =================================================

# Load Haar Cascade classifier
face_cascade = None
try:
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + HAAR_CASCADE_PATH)
    if face_cascade.empty():
        print(f"Warning: Could not load Haar Cascade from {HAAR_CASCADE_PATH}")
        face_cascade = None
except Exception as e:
    print(f"Warning: Error loading Haar Cascade: {e}")
    face_cascade = None

def detect_faces(image_path: Path) -> Tuple[bool, Optional[Tuple[int, int, int, int]]]:
    """
    Detect faces in image using Haar Cascade.
    Returns (has_valid_face, face_bbox) where bbox is (x, y, w, h)
    """
    if face_cascade is None:
        return False, None
    
    try:
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return False, None
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(MIN_FACE_WIDTH, MIN_FACE_HEIGHT)
        )
        
        # Check if any valid face found
        if len(faces) > 0:
            # Return largest face
            largest_face = max(faces, key=lambda f: f[2] * f[3])  # max by area
            return True, tuple(largest_face)
        
        return False, None
        
    except Exception as e:
        return False, None

def calculate_blur_score(image_path: Path) -> float:
    """Calculate blur score using variance of Laplacian."""
    try:
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        
        # Calculate Laplacian variance
        laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
        return laplacian_var
        
    except Exception:
        return 0.0

def calculate_brightness(image_path: Path) -> float:
    """Calculate mean brightness of image."""
    try:
        img = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            return 0.0
        
        return float(np.mean(img))
        
    except Exception:
        return 0.0

def is_valid_image_with_filters(image_path: Path) -> Tuple[bool, str]:
    """
    Check if image file is valid and meets all filtering criteria.
    Returns (is_valid, reason_for_skip)
    """
    try:
        # First check if image is readable with PIL
        with Image.open(image_path) as img:
            img.verify()
        
        # Face detection
        has_face, face_bbox = detect_faces(image_path)
        if not has_face:
            return False, "no face detected"
        
        # Blur detection
        blur_score = calculate_blur_score(image_path)
        if blur_score < BLUR_THRESHOLD:
            return False, f"too blurry (score: {blur_score:.1f})"
        
        # Brightness check
        brightness = calculate_brightness(image_path)
        if brightness < MIN_BRIGHTNESS:
            return False, f"too dark (brightness: {brightness:.1f})"
        if brightness > MAX_BRIGHTNESS:
            return False, f"too bright (brightness: {brightness:.1f})"
        
        return True, ""
        
    except Exception as e:
        return False, f"corrupted/unreadable: {str(e)[:50]}"

def discover_images(input_dir: Path) -> list:
    """Discover all image files in input directory recursively."""
    print(f"Scanning {input_dir} for images...")
    
    if not input_dir.exists():
        print(f"Error: Input directory {input_dir} does not exist!")
        return []
    
    image_files = []
    
    # Find all files with supported extensions recursively
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

def process_and_sample_images(image_files: list, output_path: Path) -> Tuple[int, int, int, dict]:
    """
    Process images with filters and randomly sample 50% of valid ones.
    Returns (total_scanned, after_filtering_count, final_selected_count, skip_reasons)
    """
    total_scanned = len(image_files)
    valid_images = []
    skip_reasons = {}
    
    # First pass: filter images
    for img_path in tqdm(image_files, desc="Filtering images"):
        is_valid, skip_reason = is_valid_image_with_filters(img_path)
        
        if is_valid:
            valid_images.append(img_path)
        else:
            skip_reasons[skip_reason] = skip_reasons.get(skip_reason, 0) + 1
    
    after_filtering_count = len(valid_images)
    
    # Second pass: random sampling
    if after_filtering_count > 0:
        # Set random seed for reproducibility
        random.seed(RANDOM_SEED)
        
        # Calculate how many to select
        final_count = max(1, int(after_filtering_count * SAMPLING_RATIO))
        
        # Randomly sample
        selected_images = random.sample(valid_images, final_count)
        
        # Copy selected images
        copied_count = 0
        for img_path in tqdm(selected_images, desc="Copying selected images"):
            try:
                unique_filename = get_unique_filename(output_path, img_path.name)
                dest_path = output_path / unique_filename
                shutil.copy2(img_path, dest_path)
                copied_count += 1
            except Exception as e:
                print(f"Warning: Failed to copy {img_path}: {e}")
        
        return total_scanned, after_filtering_count, copied_count, skip_reasons
    
    return total_scanned, after_filtering_count, 0, skip_reasons

def main():
    """Main function to clean and copy teenage face images."""
    print("=== Teenage Faces Cleaner ===")
    print(f"Input path: {INPUT_PATH}")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Minimum face size: {MIN_FACE_WIDTH}x{MIN_FACE_HEIGHT}")
    print(f"Blur threshold: {BLUR_THRESHOLD}")
    print(f"Brightness range: {MIN_BRIGHTNESS}-{MAX_BRIGHTNESS}")
    print(f"Sampling ratio: {SAMPLING_RATIO*100:.0f}%")
    print(f"Random seed: {RANDOM_SEED}")
    print()
    
    if face_cascade is None:
        print("Error: Haar Cascade classifier not available!")
        print("Please ensure OpenCV is properly installed with Haar Cascade files.")
        return
    
    # Discover all images
    image_files = discover_images(INPUT_PATH)
    
    if not image_files:
        print("No images found in input directory!")
        return
    
    # Ensure output directory exists
    ensure_output_directory(OUTPUT_PATH)
    
    # Process and sample images
    total_scanned, after_filtering, final_selected, skip_reasons = process_and_sample_images(image_files, OUTPUT_PATH)
    
    print()
    print("=== Summary ===")
    print(f"Total images scanned: {total_scanned}")
    print(f"After filtering count: {after_filtering}")
    print(f"Final selected count: {final_selected}")
    
    # Print skip reasons summary
    if skip_reasons:
        print("\nSkip reasons:")
        for reason, count in skip_reasons.items():
            print(f"  {reason}: {count}")
    
    print(f"Output directory: {OUTPUT_PATH}")
    print("Done!")

if __name__ == "__main__":
    main()
