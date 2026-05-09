import os
import random
import sys

import cv2
import torch
from PIL import Image


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(os.path.dirname(SCRIPT_DIR), "src")
if SRC_DIR not in sys.path:
    sys.path.append(SRC_DIR)

import config  # noqa: E402
from model import DeepfakeClassifier  # noqa: E402
from preprocess import get_transforms  # noqa: E402


LABEL_TO_NAME = {0: "real", 1: "fake"}


def load_image_from_path(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in {".jpg", ".jpeg", ".png"}:
        return Image.open(path).convert("RGB")

    cap = cv2.VideoCapture(path)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise ValueError(f"Could not read first frame from: {path}")
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame)


def collect_test_samples(test_dir):
    allowed_exts = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v", ".jpg", ".jpeg", ".png"}
    samples = []
    for label_name, label in (("real", 0), ("fake", 1)):
        class_dir = os.path.join(test_dir, label_name)
        if not os.path.isdir(class_dir):
            continue
        for name in os.listdir(class_dir):
            if os.path.splitext(name)[1].lower() in allowed_exts:
                samples.append((os.path.join(class_dir, name), label))
    return samples


def main():
    model_path = os.path.join(config.BASE_DIR, "models", "model.pth")
    if not os.path.isfile(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    if not os.path.isdir(config.TEST_DIR):
        raise FileNotFoundError(f"Test directory not found: {config.TEST_DIR}")

    samples = collect_test_samples(config.TEST_DIR)
    if not samples:
        raise ValueError(f"No test samples found in: {config.TEST_DIR}")

    _, val_transform = get_transforms()
    picked = random.sample(samples, min(5, len(samples)))

    model = DeepfakeClassifier(pretrained=False).to(config.DEVICE)
    state = torch.load(model_path, map_location=config.DEVICE)
    model.load_state_dict(state)
    model.eval()

    print("filename | actual | predicted | confidence")
    with torch.no_grad():
        for path, actual in picked:
            image = load_image_from_path(path)
            x = val_transform(image).unsqueeze(0).to(config.DEVICE)
            logits = model(x)
            probs = torch.softmax(logits, dim=1)[0]
            pred = int(torch.argmax(probs).item())
            conf = float(probs[pred].item())
            print(f"{os.path.basename(path)} | {LABEL_TO_NAME[actual]} | {LABEL_TO_NAME[pred]} | {conf:.4f}")


if __name__ == "__main__":
    main()
