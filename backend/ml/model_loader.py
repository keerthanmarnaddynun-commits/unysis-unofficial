import logging
import sys
from pathlib import Path
from threading import Lock
from typing import Optional

from .config import MODEL_PATH


LOGGER = logging.getLogger(__name__)
_MODEL = None
_MODEL_LOCK = Lock()


def _load_model_class():
    src_dir = Path(__file__).resolve().parents[2] / "ml_pipeline" / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from model import DeepfakeClassifier  # type: ignore

    return DeepfakeClassifier


def get_model():
    global _MODEL

    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL

        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Model weights not found: {MODEL_PATH}")

        import torch
        device = get_device()
        DeepfakeClassifier = _load_model_class()
        model = DeepfakeClassifier(pretrained=False).to(device)

        checkpoint = torch.load(MODEL_PATH, map_location=device)
        state_dict = checkpoint.get("model_state_dict", checkpoint) if isinstance(checkpoint, dict) else checkpoint
        model.load_state_dict(state_dict)
        model.eval()

        _MODEL = model
        LOGGER.info("Model loaded from %s on device %s", MODEL_PATH, device)
        return _MODEL


def get_device():
    import torch
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")

