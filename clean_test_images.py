from pathlib import Path
from typing import Literal, Optional, Tuple, Union

import torch
from facenet_pytorch import MTCNN
from PIL import Image


INPUT_DIR = Path("test_images")
OUTPUT_DIR = Path("test_images_clean")
TARGET_SIZE = (224, 224)
MARGIN_RATIO = 0.15  # 15% margin around detected face
VALID_EXTS = {".jpg", ".jpeg", ".png", ".webp"}


DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# Global singleton detector; initialized once.
DETECTOR = MTCNN(keep_all=True, device=DEVICE)


def expand_bbox(
    box: Tuple[float, float, float, float],
    width: int,
    height: int,
    margin_ratio: float,
) -> Tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    mx = bw * margin_ratio
    my = bh * margin_ratio

    nx1 = max(0, int(round(x1 - mx)))
    ny1 = max(0, int(round(y1 - my)))
    nx2 = min(width, int(round(x2 + mx)))
    ny2 = min(height, int(round(y2 + my)))
    return nx1, ny1, nx2, ny2


def unique_output_path(base_name: str, suffix: str) -> Path:
    candidate = OUTPUT_DIR / f"{base_name}_clean{suffix}"
    idx = 1
    while candidate.exists():
        candidate = OUTPUT_DIR / f"{base_name}_clean_{idx}{suffix}"
        idx += 1
    return candidate


ProcessResult = Union[Image.Image, Literal["NO_FACE", "MULTI_FACE"], None]


def process_image(path: Path) -> ProcessResult:
    try:
        with Image.open(path) as img:
            image = img.convert("RGB")
    except Exception:
        return None

    try:
        boxes, _ = DETECTOR.detect(image)
    except Exception:
        return None

    if boxes is None or len(boxes) == 0:
        return "NO_FACE"  # sentinel
    if len(boxes) > 1:
        return "MULTI_FACE"  # sentinel

    width, height = image.size
    x1, y1, x2, y2 = expand_bbox(tuple(boxes[0]), width, height, MARGIN_RATIO)
    if x2 <= x1 or y2 <= y1:
        return None

    face = image.crop((x1, y1, x2, y2)).resize(TARGET_SIZE, Image.Resampling.BILINEAR)
    return face


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    input_abs = INPUT_DIR.resolve()
    exists = INPUT_DIR.exists()
    print(f"input_folder_abs_path: {input_abs}")
    print(f"input_folder_exists: {exists}")

    if not exists:
        print("total_files_found: 0")
        print(f"Input directory not found: {input_abs}")
        return

    files = [p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in VALID_EXTS]
    print(f"total_files_found: {len(files)}")

    total_processed = 0
    skipped_no_face = 0
    skipped_multiple_faces = 0
    skipped_error = 0
    saved_single_face = 0

    for path in files:
        total_processed += 1
        print(f"processing: {path.name}")
        result = process_image(path)

        if result == "NO_FACE":
            skipped_no_face += 1
            continue
        if result == "MULTI_FACE":
            skipped_multiple_faces += 1
            continue
        if result is None:
            skipped_error += 1
            continue

        out_path = unique_output_path(path.stem, ".jpg")
        result.save(out_path, format="JPEG", quality=95)
        saved_single_face += 1

    print(f"total_images_processed: {total_processed}")
    print(f"skipped_no_face: {skipped_no_face}")
    print(f"skipped_multiple_faces: {skipped_multiple_faces}")
    print(f"saved_single_face: {saved_single_face}")
    print(f"skipped_error: {skipped_error}")
    print(f"output_dir: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()
