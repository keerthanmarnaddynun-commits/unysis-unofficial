#!/usr/bin/env python3
"""Script to organize test images into a unified folder structure.

Moves and renames images from `test_real_images/` and `test_fake_images/` into:
    test_images/
       real/
       fake/
"""

import shutil
from pathlib import Path


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def organize_category(src_dir: Path, dest_dir: Path, prefix: str, repo_root: Path) -> None:
    if not src_dir.is_dir():
        print(f"[!] Source directory not found: {src_dir}")
        return

    # Collect and sort image files
    files = []
    for p in src_dir.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            files.append(p)
    files.sort(key=lambda x: x.name)

    if not files:
        print(f"[*] No images found in {src_dir}")
        return

    dest_dir.mkdir(parents=True, exist_ok=True)

    for idx, old_path in enumerate(files, start=1):
        suffix = old_path.suffix
        new_name = f"{prefix}_{idx}{suffix}"
        new_path = dest_dir / new_name

        try:
            # Move the file safely
            shutil.move(str(old_path), str(new_path))
            
            # Format output matching the user's request using forward slashes
            old_rel = old_path.relative_to(repo_root) if old_path.is_relative_to(repo_root) else old_path
            new_rel = new_path.relative_to(repo_root) if new_path.is_relative_to(repo_root) else new_path
            old_str = str(old_rel).replace("\\", "/")
            new_str = str(new_rel).replace("\\", "/")
            print(f"{old_str} → {new_str}")
        except Exception as e:
            print(f"[!] Error moving {old_path} to {new_path}: {e}")


def main() -> None:
    repo_root = Path(__file__).parent.resolve()
    
    src_real = repo_root / "test_real_images"
    src_fake = repo_root / "test_fake_images"
    
    dest_real = repo_root / "test_images" / "real"
    dest_fake = repo_root / "test_images" / "fake"
    
    print("[*] Organizing real images...")
    organize_category(src_real, dest_real, "real", repo_root)
    
    print("\n[*] Organizing fake images...")
    organize_category(src_fake, dest_fake, "fake", repo_root)


if __name__ == "__main__":
    main()
