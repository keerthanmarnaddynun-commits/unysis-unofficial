import os
import random
import shutil
import uuid
from pathlib import Path
from PIL import Image
from tqdm import tqdm

# ==========================================
# CONFIGURATION
# ==========================================

# STYLEGAN_PATH = r"d:\forsen\Style3GAN\Fake faces"
STYLEGAN_PATH = r"C:\Users\Kirthan\Desktop\bharatshield round 1\Style3GAN\Fake faces"

# Output structure will be: OUTPUT_PATH / "fake" / "gan"
OUTPUT_PATH = "final_dataset"

SAMPLE_SIZE = 10000
RANDOM_SEED = 42

# Allowed valid image extensions
VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

def is_valid_image(file_path: Path) -> bool:
    """
    Verify if the file is a valid, uncorrupted image using PIL.
    """
    try:
        with Image.open(file_path) as img:
            img.verify()
        return True
    except Exception:
        return False

def main():
    print("Initializing StyleGAN dataset sampling...")
    random.seed(RANDOM_SEED)
    
    input_dir = Path(STYLEGAN_PATH)
    output_dir = Path(OUTPUT_PATH) / "fake" / "gan"
    
    # 1. Safety & validation
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: Input directory '{STYLEGAN_PATH}' does not exist or is not a directory.")
        print("Please update STYLEGAN_PATH in the script configuration.")
        return

    # 2. Scanning for potential images
    print(f"Scanning for image files recursively in '{input_dir}'...")
    potential_images = []
    
    # Use rglob to find all files and filter by valid extensions initially
    for file_path in input_dir.rglob("*"):
        if file_path.is_file() and file_path.suffix.lower() in VALID_EXTENSIONS:
            potential_images.append(file_path)
            
    total_found = len(potential_images)
    print(f"Total potential image files found: {total_found}")
    
    if total_found == 0:
        print("No valid image files found. Exiting.")
        return

    # 3. Random selection & Verification
    # We shuffle first, then pick up to SAMPLE_SIZE valid images, discarding corrupted ones.
    random.shuffle(potential_images)
    
    selected_images = []
    print("\nVerifying images and selecting sample...")
    
    # Progress bar for the verification & selection process
    with tqdm(total=min(SAMPLE_SIZE, total_found), desc="Selecting valid images") as pbar:
        for file_path in potential_images:
            # Skip if it fails PIL verification
            if is_valid_image(file_path):
                selected_images.append(file_path)
                pbar.update(1)
                
                # Stop if we have reached our target sample size
                if len(selected_images) == SAMPLE_SIZE:
                    break
    
    total_selected = len(selected_images)
    print(f"\nTotal valid images successfully verified and selected: {total_selected}")
    
    if total_selected == 0:
        print("No valid (uncorrupted) images found. Exiting.")
        return

    # 4. Preparing Output Directory
    # Ensure safe write operations ONLY in final_dataset/fake/gan
    print(f"\nPreparing output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 5. Copying files safely
    copied_count = 0
    existing_filenames = set()
    
    print("Copying images to output directory...")
    for file_path in tqdm(selected_images, desc="Copying images"):
        filename = file_path.name
        
        # Handle duplicate filenames using UUID to avoid overwrite
        if filename in existing_filenames:
            name = file_path.stem
            ext = file_path.suffix
            filename = f"{name}_{uuid.uuid4().hex[:8]}{ext}"
            
        # Add to tracked filenames to prevent future conflicts
        existing_filenames.add(filename)
        dest_path = output_dir / filename
        
        try:
            # Safe read/write: copy2 preserves metadata, reads from input, writes to dest
            shutil.copy2(file_path, dest_path)
            copied_count += 1
        except Exception as e:
            print(f"Failed to copy {file_path.name}: {e}")
            
    # 6. Final report
    print("\n" + "="*40)
    print("SAMPLING COMPLETE")
    print("="*40)
    print(f"Total potential images found: {total_found}")
    print(f"Target sample size:           {SAMPLE_SIZE}")
    print(f"Total valid images selected:  {total_selected}")
    print(f"Total images copied safely:   {copied_count}")
    print(f"Output directory:             {output_dir.absolute()}")

if __name__ == "__main__":
    main()
