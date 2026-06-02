#!/usr/bin/env python3
"""
RIR Faces Cleaner

Filters and extracts high-quality real face images from real_images_run dataset 
using OpenCV face detection and quality filters.
"""

import os
import shutil
import uuid
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
from tqdm import tqdm

# ============ CONFIGURABLE VARIABLES ============
INPUT_PATH = Path("real_images_run")  # Source directory
OUTPUT_PATH = Path("final_dataset/real/rir")  # Target directory
MIN_FACE_WIDTH = 80  # Minimum face width in pixels
MIN_FACE_HEIGHT = 80  # Minimum face height in pixels
BLUR_THRESHOLD = 100  # Variance of Laplacian threshold (lower = blurrier)
MIN_BRIGHTNESS = 40  # Minimum mean brightness
MAX_BRIGHTNESS = 220  # Maximum mean brightness
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
            # Return the largest face
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
    """Discover all image files in the input directory recursively."""
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

def copy_images_safely(image_files: list, output_path: Path) -> Tuple[int, int, dict]:
    """
    Process and copy images safely with filtering.
    Returns (copied_count, skipped_count, skip_reasons)
    """
    copied_count = 0
    skipped_count = 0
    skip_reasons = {}
    faces_detected_count = 0
    
    for img_path in tqdm(image_files, desc="Processing images"):
        is_valid, skip_reason = is_valid_image_with_filters(img_path)
        
        # Check if face was detected (even if image was skipped for other reasons)
        has_face, _ = detect_faces(img_path)
        if has_face:
            faces_detected_count += 1
        
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
    
    return copied_count, skipped_count, skip_reasons

def main():
    """Main function to clean and copy RIR face images."""
    print("=== RIR Faces Cleaner ===")
    print(f"Input path: {INPUT_PATH}")
    print(f"Output path: {OUTPUT_PATH}")
    print(f"Minimum face size: {MIN_FACE_WIDTH}x{MIN_FACE_HEIGHT}")
    print(f"Blur threshold: {BLUR_THRESHOLD}")
    print(f"Brightness range: {MIN_BRIGHTNESS}-{MAX_BRIGHTNESS}")
    print()
    
    if face_cascade is None:
        print("Error: Haar Cascade classifier not available!")
        print("Please ensure OpenCV is properly installed with Haar Cascade files.")
        return
    
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
    copied_count, skipped_count, skip_reasons = copy_images_safely(image_files, OUTPUT_PATH)
    
    # Count faces detected separately
    faces_detected = 0
    for img_path in image_files:
        has_face, _ = detect_faces(img_path)
        if has_face:
            faces_detected += 1
    
    print()
    print("=== Summary ===")
    print(f"Total images scanned: {total_scanned}")
    print(f"Images with faces detected: {faces_detected}")
    print(f"Valid images copied: {copied_count}")
    print(f"Images skipped: {skipped_count}")
    
    # Print skip reasons summary
    if skip_reasons:
        print("\nSkip reasons:")
        for reason, count in skip_reasons.items():
            print(f"  {reason}: {count}")
    
    print(f"Output directory: {OUTPUT_PATH}")
    print("Done!")

if __name__ == "__main__":
    main()
