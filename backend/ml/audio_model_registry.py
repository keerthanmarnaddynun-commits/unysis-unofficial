import os
from pathlib import Path

# Base directory for the backend
BACKEND_DIR = Path(__file__).resolve().parent.parent
# Forsen directory
FORSEN_DIR = BACKEND_DIR.parent

AVAILABLE_MODELS = {
    "aasist": {
        "name": "AASIST",
        "version": "official",
        "architecture_module": "models.AASIST",
        "checkpoint_path": str(FORSEN_DIR / "aasist" / "models" / "weights" / "AASIST.pth"),
        "config_path": str(FORSEN_DIR / "aasist" / "config" / "AASIST.conf"),
        "expected_sample_rate": 16000,
        "input_length": 64600  # About 4.03 seconds
    },
    "aasist_large": {
        "name": "AASIST-L",
        "version": "official_large",
        "architecture_module": "models.AASIST",
        "checkpoint_path": str(FORSEN_DIR / "aasist" / "models" / "weights" / "AASIST-L.pth"),
        "config_path": str(FORSEN_DIR / "aasist" / "config" / "AASIST.conf"), # Assume same config structure
        "expected_sample_rate": 16000,
        "input_length": 64600
    },
    "heuristic": {
        "name": "Heuristic Audio Detector",
        "version": "v1.0.0",
        "architecture_module": None,
        "checkpoint_path": None,
        "config_path": None,
        "expected_sample_rate": 16000,
        "input_length": None
    }
}

ACTIVE_MODEL = "aasist"  # Which model to load primarily
