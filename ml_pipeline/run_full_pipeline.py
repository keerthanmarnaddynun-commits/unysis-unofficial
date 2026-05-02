import os
import sys
import shutil
import random
import traceback
from pathlib import Path

import cv2
import torch
import torch.nn as nn
import torch.optim as optim
from PIL import Image
from sklearn.metrics import confusion_matrix
from torch.utils.data import DataLoader, Dataset, random_split
from tqdm import tqdm


ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

import config  # noqa: E402
from evaluate import compute_metrics  # noqa: E402
from model import DeepfakeClassifier  # noqa: E402
from preprocess import get_transforms  # noqa: E402
from utils import calculate_class_weights  # noqa: E402


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}
N_FRAMES_PER_VIDEO = 15


def log_line(log_file: Path, message: str) -> None:
    print(message)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def clear_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def safe_copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    target = dst
    i = 1
    while target.exists():
        target = target.with_name(f"{dst.stem}_{i}{dst.suffix}")
        i += 1
    shutil.copy2(src, target)
    return target


def find_dataset_root() -> Path:
    dataset_root = Path(config.DATASET_BASE_DIR)
    if not dataset_root.exists():
        raise FileNotFoundError(f"Dataset root not found: {dataset_root}")
    for split in ("train", "test"):
        for cls in ("real", "fake"):
            p = dataset_root / split / cls
            if not p.exists():
                raise FileNotFoundError(f"Missing required dataset folder: {p}")
    return dataset_root


def step1_extract_frames(dataset_root: Path, processed_root: Path, log_file: Path):
    log_line(log_file, "=== STEP 1: Controlled Frame Extraction ===")
    frames_root = processed_root / "frames"
    clear_dir(frames_root)

    counts = {"train": {"real": 0, "fake": 0}, "test": {"real": 0, "fake": 0}}
    for split in ("train", "test"):
        for cls in ("real", "fake"):
            src_dir = dataset_root / split / cls
            out_dir = frames_root / split / cls
            out_dir.mkdir(parents=True, exist_ok=True)
            video_files = [
                p for p in src_dir.iterdir()
                if p.is_file() and p.suffix.lower() in VIDEO_EXTS
            ]
            for video_path in tqdm(video_files, desc=f"Extract {split}/{cls}"):
                cap = cv2.VideoCapture(str(video_path))
                total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total <= 0:
                    cap.release()
                    continue

                indices = sorted(set(int(x) for x in torch.linspace(0, total - 1, N_FRAMES_PER_VIDEO).tolist()))
                idx_set = set(indices)
                frame_idx = 0
                saved_idx = 0
                base_name = video_path.stem
                while cap.isOpened():
                    ok, frame = cap.read()
                    if not ok:
                        break
                    if frame_idx in idx_set:
                        saved_idx += 1
                        out_name = f"{base_name}_frame_{saved_idx:02d}.jpg"
                        out_path = out_dir / out_name
                        if out_path.exists():
                            out_path = out_dir / f"{base_name}_{video_path.stat().st_size}_frame_{saved_idx:02d}.jpg"
                        cv2.imwrite(str(out_path), frame)
                        counts[split][cls] += 1
                    frame_idx += 1
                cap.release()

    log_line(
        log_file,
        (
            f"Frames extracted - train real: {counts['train']['real']}, "
            f"train fake: {counts['train']['fake']}, "
            f"test real: {counts['test']['real']}, test fake: {counts['test']['fake']}"
        ),
    )
    return counts


def step2_face_crop(processed_root: Path, log_file: Path):
    log_line(log_file, "=== STEP 2: Optional Face Cropping ===")
    frames_root = processed_root / "frames"
    faces_root = processed_root / "faces"
    clear_dir(faces_root)

    detector = None
    try:
        from facenet_pytorch import MTCNN  # type: ignore
        detector = MTCNN(keep_all=False, device=config.DEVICE)
        log_line(log_file, "Face detector: MTCNN enabled.")
    except Exception:
        log_line(log_file, "Face detector unavailable. Copying original frames as fallback.")

    detected = 0
    skipped = 0

    for split in ("train", "test"):
        for cls in ("real", "fake"):
            src_dir = frames_root / split / cls
            out_dir = faces_root / split / cls
            out_dir.mkdir(parents=True, exist_ok=True)
            if not src_dir.exists():
                continue
            for frame_path in tqdm(list(src_dir.glob("*.jpg")), desc=f"Face {split}/{cls}"):
                out_path = out_dir / frame_path.name
                if detector is None:
                    shutil.copy2(frame_path, out_path)
                    skipped += 1
                    continue

                image_bgr = cv2.imread(str(frame_path))
                if image_bgr is None:
                    skipped += 1
                    continue
                image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(image_rgb)
                boxes, _ = detector.detect(pil_img)

                if boxes is not None and len(boxes) > 0:
                    x1, y1, x2, y2 = boxes[0].astype(int)
                    h, w = image_bgr.shape[:2]
                    x1, y1 = max(0, x1), max(0, y1)
                    x2, y2 = min(w, x2), min(h, y2)
                    crop = image_bgr[y1:y2, x1:x2]
                    if crop.size > 0:
                        cv2.imwrite(str(out_path), crop)
                        detected += 1
                    else:
                        shutil.copy2(frame_path, out_path)
                        skipped += 1
                else:
                    shutil.copy2(frame_path, out_path)
                    skipped += 1

    log_line(log_file, f"Faces detected: {detected}, skipped/copied: {skipped}")
    return {"detected": detected, "skipped": skipped}


def step3_build_final_dataset(processed_root: Path, log_file: Path):
    log_line(log_file, "=== STEP 3: Build Final Dataset ===")
    faces_root = processed_root / "faces"
    frames_root = processed_root / "frames"
    final_root = processed_root / "final"
    clear_dir(final_root)

    face_count = sum(1 for _ in faces_root.rglob("*.jpg")) if faces_root.exists() else 0
    chosen_root = faces_root if face_count > 0 else frames_root
    log_line(log_file, f"Using source for final dataset: {chosen_root}")

    for split in ("train", "test"):
        for cls in ("real", "fake"):
            src_dir = chosen_root / split / cls
            out_dir = final_root / split / cls
            out_dir.mkdir(parents=True, exist_ok=True)
            if not src_dir.exists():
                continue
            for src in src_dir.glob("*.jpg"):
                safe_copy(src, out_dir / src.name)

    summary = {
        "train": {
            "real": len(list((final_root / "train" / "real").glob("*.jpg"))),
            "fake": len(list((final_root / "train" / "fake").glob("*.jpg"))),
        },
        "test": {
            "real": len(list((final_root / "test" / "real").glob("*.jpg"))),
            "fake": len(list((final_root / "test" / "fake").glob("*.jpg"))),
        },
    }
    log_line(
        log_file,
        (
            f"Final dataset summary - train real: {summary['train']['real']}, "
            f"train fake: {summary['train']['fake']}, "
            f"test real: {summary['test']['real']}, test fake: {summary['test']['fake']}"
        ),
    )
    return final_root, summary


class ImageDataset(Dataset):
    def __init__(self, samples, labels, transform=None):
        self.samples = samples
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        path = self.samples[idx]
        label = self.labels[idx]
        image = Image.open(path).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label


def build_loaders_from_final(final_root: Path):
    train_real = list((final_root / "train" / "real").glob("*.jpg"))
    train_fake = list((final_root / "train" / "fake").glob("*.jpg"))
    test_real = list((final_root / "test" / "real").glob("*.jpg"))
    test_fake = list((final_root / "test" / "fake").glob("*.jpg"))

    train_samples = train_real + train_fake
    train_labels = [0] * len(train_real) + [1] * len(train_fake)

    test_samples = test_real + test_fake
    test_labels = [0] * len(test_real) + [1] * len(test_fake)

    if len(train_samples) == 0 or len(test_samples) == 0:
        raise ValueError("Final dataset is empty for train or test.")

    train_t, val_t = get_transforms()
    base_train = ImageDataset(train_samples, train_labels, transform=None)

    val_ratio = config.VAL_SPLIT_RATIO if hasattr(config, "VAL_SPLIT_RATIO") else 0.12
    val_size = max(1, int(len(base_train) * val_ratio))
    train_size = len(base_train) - val_size
    train_subset, val_subset = random_split(
        base_train,
        [train_size, val_size],
        generator=torch.Generator().manual_seed(getattr(config, "RANDOM_SEED", 42)),
    )

    sub_train_samples = [base_train.samples[i] for i in train_subset.indices]
    sub_train_labels = [base_train.labels[i] for i in train_subset.indices]
    sub_val_samples = [base_train.samples[i] for i in val_subset.indices]
    sub_val_labels = [base_train.labels[i] for i in val_subset.indices]

    train_dataset = ImageDataset(sub_train_samples, sub_train_labels, transform=train_t)
    val_dataset = ImageDataset(sub_val_samples, sub_val_labels, transform=val_t)
    test_dataset = ImageDataset(test_samples, test_labels, transform=val_t)

    batch_size = 16 if getattr(config, "BATCH_SIZE", 32) < 16 else 32
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4, pin_memory=True if config.DEVICE == "cuda" else False)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=4, pin_memory=True if config.DEVICE == "cuda" else False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=4, pin_memory=True if config.DEVICE == "cuda" else False)

    return train_loader, val_loader, test_loader, sub_train_labels


def evaluate_loader(model, loader, criterion):
    model.eval()
    total_loss = 0.0
    y_true = []
    y_pred = []
    y_conf = []
    with torch.no_grad():
        for images, labels in loader:
            images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
            outputs = model(images)
            loss = criterion(outputs, labels)
            probs = torch.softmax(outputs, dim=1)
            confs, preds = torch.max(probs, 1)
            total_loss += loss.item()
            y_true.extend(labels.cpu().tolist())
            y_pred.extend(preds.cpu().tolist())
            y_conf.extend(confs.cpu().tolist())
    metrics = compute_metrics(y_true, y_pred) if y_true else {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1": 0.0}
    return total_loss / max(len(loader), 1), metrics, y_true, y_pred, y_conf


def step4_5_6_train_validate_test(final_root: Path, log_file: Path):
    log_line(log_file, "=== STEP 4/5/6: Train, Validate, Test ===")
    train_loader, val_loader, test_loader, train_labels = build_loaders_from_final(final_root)

    model = DeepfakeClassifier(pretrained=True).to(config.DEVICE)
    class_weights = calculate_class_weights(train_labels).to(config.DEVICE)
    criterion = nn.CrossEntropyLoss(weight=class_weights)
    optimizer = optim.Adam(model.parameters(), lr=2e-4)

    epochs = min(max(getattr(config, "NUM_EPOCHS", 10), 10), 15)
    best_val_acc = 0.0

    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0
        correct = 0
        total = 0
        for images, labels in tqdm(train_loader, desc=f"Epoch {epoch}/{epochs} [Train]"):
            images, labels = images.to(config.DEVICE), labels.to(config.DEVICE)
            optimizer.zero_grad()
            outputs = model(images)
            loss = criterion(outputs, labels)
            loss.backward()
            optimizer.step()
            running_loss += loss.item()
            _, preds = torch.max(outputs, 1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

        train_acc = correct / max(total, 1)
        train_loss = running_loss / max(len(train_loader), 1)
        val_loss, val_metrics, _, _, _ = evaluate_loader(model, val_loader, criterion)
        log_line(
            log_file,
            (
                f"Epoch {epoch}/{epochs} - "
                f"train_acc: {train_acc:.4f}, val_acc: {val_metrics['accuracy']:.4f}, "
                f"loss: {train_loss:.4f}, val_loss: {val_loss:.4f}"
            ),
        )
        if val_metrics["accuracy"] > best_val_acc:
            best_val_acc = val_metrics["accuracy"]

    model_path = ROOT / "models" / "frame_model.pth"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), model_path)
    log_line(log_file, f"Model saved: {model_path}")

    # Step 5 validation metrics
    val_loss, val_metrics, _, _, _ = evaluate_loader(model, val_loader, criterion)
    log_line(log_file, f"Validation metrics - loss: {val_loss:.4f}, metrics: {val_metrics}")

    # Step 6 testing metrics + sample inference
    test_loss, test_metrics, y_true, y_pred, y_conf = evaluate_loader(model, test_loader, criterion)
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1]).tolist() if y_true else [[0, 0], [0, 0]]
    pred_real = sum(1 for p in y_pred if p == 0)
    pred_fake = sum(1 for p in y_pred if p == 1)
    log_line(log_file, f"Test loss: {test_loss:.4f}")
    log_line(log_file, f"Test metrics: {test_metrics}")
    log_line(log_file, f"Confusion matrix [[TN, FP], [FN, TP]]: {cm}")
    log_line(log_file, f"Prediction counts - real: {pred_real}, fake: {pred_fake}")

    log_line(log_file, "Random 5 sample inferences:")
    test_samples = list(zip(test_loader.dataset.samples, test_loader.dataset.labels))
    sampled = random.sample(test_samples, min(5, len(test_samples)))
    _, val_t = get_transforms()
    model.eval()
    for path, actual in sampled:
        image = Image.open(path).convert("RGB")
        x = val_t(image).unsqueeze(0).to(config.DEVICE)
        with torch.no_grad():
            out = model(x)
            probs = torch.softmax(out, dim=1)[0]
            pred = int(torch.argmax(probs).item())
            conf = float(probs[pred].item())
        actual_name = "real" if actual == 0 else "fake"
        pred_name = "real" if pred == 0 else "fake"
        log_line(log_file, f"{Path(path).name} | {actual_name} | {pred_name} | {conf:.4f}")


def run_pipeline():
    log_file = ROOT / "logs" / "pipeline_log.txt"
    processed_root = ROOT / "processed_data"
    processed_root.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as f:
        f.write("\n" + "=" * 70 + "\n")
        f.write("Starting full pipeline run\n")

    try:
        dataset_root = find_dataset_root()
        log_line(log_file, f"Dataset root: {dataset_root}")
        log_line(log_file, f"Processed root: {processed_root}")

        step1_extract_frames(dataset_root, processed_root, log_file)
        step2_face_crop(processed_root, log_file)
        final_root, _ = step3_build_final_dataset(processed_root, log_file)
        step4_5_6_train_validate_test(final_root, log_file)

        final_msg = (
            "Pipeline completed successfully.\n"
            "Check ml_pipeline/logs/pipeline_log.txt for full report."
        )
        log_line(log_file, final_msg)
    except Exception as e:
        log_line(log_file, f"Pipeline failed: {e}")
        log_line(log_file, traceback.format_exc())
        raise


if __name__ == "__main__":
    run_pipeline()
