import sys
import time
import json
import torch
import importlib
from datetime import datetime
from pathlib import Path

from ml.audio_model_registry import AVAILABLE_MODELS, ACTIVE_MODEL

# Add AASIST repo to path so we can import its modules
BACKEND_DIR = Path(__file__).resolve().parent.parent
FORSEN_DIR = BACKEND_DIR.parent
AASIST_DIR = FORSEN_DIR / "aasist"

if str(AASIST_DIR) not in sys.path:
    sys.path.append(str(AASIST_DIR))

class AudioModelLoader:
    _instance = None
    _model = None
    _model_info = None
    _load_time_ms = 0
    _device = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AudioModelLoader, cls).__new__(cls)
            cls._instance._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        return cls._instance

    def load_audio_model(self, model_key=ACTIVE_MODEL):
        if self._model is not None:
            return self._model
            
        print(f"[{datetime.now()}] [AUDIO MODEL LOAD BEGIN]")
        start_t = time.time()
        
        if model_key not in AVAILABLE_MODELS:
            raise ValueError(f"Model {model_key} not in registry.")
            
        self._model_info = AVAILABLE_MODELS[model_key]
        
        if self._model_info["architecture_module"] is None:
            # Heuristic model has no weights
            self._model = "heuristic"
            self._load_time_ms = int((time.time() - start_t) * 1000)
            print(f"[{datetime.now()}] [AUDIO MODEL LOAD END] Heuristic loaded in {self._load_time_ms}ms")
            return self._model
            
        # Load config
        with open(self._model_info["config_path"], "r") as f:
            config = json.load(f)
            
        model_config = config["model_config"]
        
        # Import the model architecture dynamically
        module = importlib.import_module(self._model_info["architecture_module"])
        ModelClass = getattr(module, "Model")
        
        # Instantiate
        self._model = ModelClass(model_config).to(self._device)
        
        # Load weights
        ckpt_path = self._model_info["checkpoint_path"]
        state_dict = torch.load(ckpt_path, map_location=self._device)
        self._model.load_state_dict(state_dict)
        self._model.eval()
        
        self._load_time_ms = int((time.time() - start_t) * 1000)
        print(f"[{datetime.now()}] [AUDIO MODEL LOAD END] {self._model_info['name']} loaded in {self._load_time_ms}ms")
        return self._model

    def get_audio_model(self, model_key=ACTIVE_MODEL):
        if self._model is None:
            self.load_audio_model(model_key)
        return self._model, self._model_info, self._device, self._load_time_ms

def load_audio_model(model_key=ACTIVE_MODEL):
    return AudioModelLoader().load_audio_model(model_key)

def get_audio_model(model_key=ACTIVE_MODEL):
    return AudioModelLoader().get_audio_model(model_key)
