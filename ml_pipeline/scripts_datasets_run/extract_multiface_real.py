#!/usr/bin/env python3
"""
Multi-Face Extractor

Detects and extracts multiple faces from images in run2/multiple faces dataset
using OpenCV Haar Cascade with quality filtering.
"""

import os
import shutil
import uuid
import cv2
import numpy as np
from pathlib import Path
from typing import List, Tuple
from PIL import Image
from tqdm import tqdm

# ============ CONFIGURABLE VARIABLES ============
INPUT_PATH = Path("run2/multiple faces")  # Source directory
OUTPUT_PATH = Path("final_dataset/real/multiface")  # Target directory
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

def detect_all_faces(image_path: Path) -> List[Tuple[int, int, int, int]]:
    """
    Detect ALL faces in image using Haar Cascade.
    Returns list of (x, y, w, h) tuples for each detected face.
    """
    if face_cascade is None:
        return []
    
    try:
        # Read image
        img = cv2.imread(str(image_path))
        if img is None:
            return []
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(MIN_FACE_WIDTH, MIN_FACE_HEIGHT)
        )
        
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]
        
    except Exception as e:
        return []

def crop_face_region(image_path: Path, face_bbox: Tuple[int, int, int, int]) -> np.ndarray:
    """Crop face region from image."""
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return None
        
        x, y, w, h = face_bbox
        
        # Add some padding around the face
        padding = 10
        x1 = max(0, x - padding)
        y1 = max(0, y - padding)
        x2 = min(img.shape[1], x + w + padding)
        y2 = min(img.shape[0], y + h + padding)
        
        # Crop face region
        face_crop = img[y1:y2, x1:x2]
        return face_crop
        
    except Exception:
        return None

def calculate_blur_score(face_image: np.ndarray) -> float:
    """Calculate blur score using variance of Laplacian."""
    try:
        if face_image is None:
            return 0.0
        
        # Convert to grayscale
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        # Calculate Laplacian variance
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        return laplacian_var
        
    except Exception:
        return 0.0

def calculate_brightness(face_image: np.ndarray) -> float:
    """Calculate mean brightness of face image."""
    try:
        if face_image is None:
            return 0.0
        
        # Convert to grayscale
        gray = cv2.cvtColor(face_image, cv2.COLOR_BGR2GRAY)
        
        return float(np.mean(gray))
        
    except Exception:
        return 0.0

def is_valid_face_crop(face_image: np.ndarray) -> Tuple[bool, str]:
    """
    Check if face crop meets quality criteria.
    Returns (is_valid, reason_for_skip)
    """
    if face_image is None:
        return False, "failed to crop"
    
    # Check face dimensions
    height, width = face_image.shape[:2]
    if width < MIN_FACE_WIDTH or height < MIN_FACE_HEIGHT:
        return False, f"too small ({width}x{height})"
    
    # Blur detection
    blur_score = calculate_blur_score(face_image)
    if blur_score < BLUR_THRESHOLD:
        return False, f"too blurry (score: {blur_score:.1f})"
    
    # Brightness check
    brightness = calculate_brightness(face_image)
    if brightness < MIN_BRIGHTNESS:
        return False, f"too dark (brightness: {brightness:.1f})"
    if brightness > MAX_BRIGHTNESS:
        return False, f"too bright (brightness: {brightness:.1f})"
    
    return True, ""

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

def generate_unique_filename(original_name: str, face_index: int) -> str:
    """Generate unique filename for each face crop."""
    stem = Path(original_name).stem
    suffix = Path(original_name).suffix
    unique_id = str(uuid.uuid4())[:8]
    return f"{stem}_face{face_index}_{unique_id}{suffix}"

def ensure_output_directory(output_path: Path) -> None:
    """Create output directory if it doesn't exist."""
    output_path.mkdir(parents=True, exist_ok=True)

def extract_and_save_faces(image_files: list, output_path: Path) -> Tuple[int, int, int, dict]:
    """
    Extract faces from images and save valid ones.
    Returns (total_scanned, total_faces_detected, faces_kept, skip_reasons)
    """
    total_scanned = len(image_files)
    total_faces_detected = 0
    faces_kept = 0
    skip_reasons = {}
    
    for img_path in tqdm(image_files, desc="Processing images"):
        try:
            # First check if image is readable with PIL
            with Image.open(img_path) as img:
                img.verify()
            
            # Detect all faces
            faces = detect_all_faces(img_path)
            total_faces_detected += len(faces)
            
            # Process each detected face
            for i, face_bbox in enumerate(faces):
                # Crop face region
                face_crop = crop_face_region(img_path, face_bbox)
                
                # Check quality
                is_valid, skip_reason = is_valid_face_crop(face_crop)
                
                if is_valid:
                    try:
                        # Generate unique filename
                        unique_filename = generate_unique_filename(img_path.name, i)
                        dest_path = output_path / unique_filename
                        
                        # Save face crop
                        cv2.imwrite(str(dest_path), face_crop)
                        faces_kept += 1
                        
                    except Exception as e:
                        print(f"Warning: Failed to save face from {img_path}: {e}")
                        skip_reasons['save_error'] = skip_reasons.get('save_error', 0) + 1
                else:
                    skip_reasons[skip_reason] = skip_reasons.get(skip_reason, 0) + 1
            
        except Exception as e:
            print(f"Warning: Failed to process {img_path}: {e}")
            skip_reasons['processing_error'] = skip_reasons.get('processing_error', 0) + 1
    
    return total_scanned, total_faces_detected, faces_kept, skip_reasons

def main():
    """Main function to extract multiple faces from images."""
    print("=== Multi-Face Extractor ===")
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
    
    if not image_files:
        print("No images found in input directory!")
        return
    
    # Ensure output directory exists
    ensure_output_directory(OUTPUT_PATH)
    
    # Extract and save faces
    total_scanned, total_faces, faces_kept, skip_reasons = extract_and_save_faces(image_files, OUTPUT_PATH)
    
    faces_skipped = total_faces - faces_kept
    
    print()
    print("=== Summary ===")
    print(f"Total images scanned: {total_scanned}")
    print(f"Total faces detected: {total_faces}")
    print(f"Faces kept: {faces_kept}")
    print(f"Faces skipped: {faces_skipped}")
    
    # Print skip reasons summary
    if skip_reasons:
        print("\nSkip reasons:")
        for reason, count in skip_reasons.items():
            print(f"  {reason}: {count}")
    
    print(f"Output directory: {OUTPUT_PATH}")
    print("Done!")

if __name__ == "__main__":
    main()
