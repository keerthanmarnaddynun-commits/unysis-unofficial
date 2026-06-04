# =====================================================================
# 0. Global Pre-Import Monkey Patches (NumPy, dlib, & CUDA Hardware Fallbacks)
# =====================================================================
import numpy as np
if not hasattr(np, "sctypes"):
    np.sctypes = {
        "int": [np.int8, np.int16, np.int32, np.int64],
        "uint": [np.uint8, np.uint16, np.uint32, np.uint64],
        "float": [np.float16, np.float32, np.float64],
        "complex": [np.complex64, np.complex128],
        "others": [bool, object, str, bytes]
    }

import dlib
class DummyShapePredictor:
    def __init__(self, *args, **kwargs): pass
    def __call__(self, *args, **kwargs): pass
dlib.shape_predictor = DummyShapePredictor

import torch
if not torch.cuda.is_available():
    class DummyDeviceProperties:
        def __init__(self):
            self.name = "Apple-Silicon-MPS-Fallback"
            self.major = 0
            self.minor = 0
            self.total_memory = 0
    torch.cuda.is_available = lambda: True
    torch.cuda.get_device_name = lambda *args, **kwargs: "Apple-Silicon-MPS-Fallback"
    torch.cuda.get_device_properties = lambda *args, **kwargs: DummyDeviceProperties()
    torch.cuda.current_device = lambda: 0

import os
import sys
import torch.nn as nn
from torchvision import transforms
from PIL import Image

# 1. Align DeepfakeBench roots in system path
base_dir = os.path.abspath("./DeepfakeBench")
sys.path.insert(0, base_dir)

# 2. Package context mocking to properly resolve relative cross-imports
import training.detectors
training.detectors.__package__ = "training.detectors"

import importlib
ucf_detector_module = importlib.import_module("training.detectors.ucf_detector")
UCFDetector = ucf_detector_module.UCFDetector

# =====================================================================
# 1.5. BYPASS REGISTRY: Instantiate Native Xception Backbone Graph
# =====================================================================
import training.networks.xception as xception_module

def custom_build_backbone(self, config):
    """Instantiates DeepfakeBench's Xception passing the required configuration block."""
    print(f"[+] Registry Bypassed: Constructing native Xception framework graph...")
    backbone_model = xception_module.Xception(config)
    return backbone_model

def bypass_build_loss(self, config):
    """Loss tracking is irrelevant for inference pipelines. Disabling."""
    print(f"[+] Inference Optimization: Bypassed loss layer configuration allocations.")
    return None

# Inject the Xception backbone builder and disable training loss calculations
UCFDetector.build_backbone = custom_build_backbone
UCFDetector.build_loss = bypass_build_loss

# =====================================================================
# 3. Hardware Target Configuration
# =====================================================================
device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
print(f"[+] Initialized Engine. Processing utilizing target device: {device}")

ucf_config = {
    'backbone_name': 'xception',
    'backbone_config': {
        'model_name': 'xception',
        'num_classes': 2,
        'pretrained': False,
        'mode': 'adjust_channel',
        'inc': 3,
        'dropout': 0.0  # Fulfills final KeyError: 'dropout'
    },
    'mode': 'adjust_channel',
    'inc': 3,
    'dropout': 0.0,    # Fulfills final KeyError: 'dropout'
    'encoder_feat_dim': 512,
    'num_classes': 2,
    'device': device,
    'loss_func': {},       
    'typeloss_func': {},
    'train_dataset': [None, None, None, None]
}

def run_native_ucf_pipeline():
    weights_path = "./DeepfakeBench/weights/ucf_best.pth"
    
    print("[*] Allocating and compiling native DeepfakeBench UCF layers...")
    model = UCFDetector(ucf_config)
    
    if os.path.exists(weights_path):
        print(f"[+] Loading trained parameters from checkpoint: {weights_path}")
        checkpoint = torch.load(weights_path, map_location=device)
        state_dict = checkpoint['model'] if 'model' in checkpoint else checkpoint
        
        clean_state_dict = {}
        for k, v in state_dict.items():
            clean_key = k.replace('module.', '')
            clean_state_dict[clean_key] = v
            
        msg = model.load_state_dict(clean_state_dict, strict=True)
        print("[+] Weight structures successfully mapped to the Xception-built model!")
    else:
        print(f"[-] Critical: Checkpoint file could not be mapped at {weights_path}")
        return

    model = model.to(device)
    model.eval()

    transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])

    folders_to_test = [
        "real_images_2",
        "fake_images_2"
    ]

    with torch.no_grad():
        for folder in folders_to_test:
            if not os.path.exists(folder):
                continue
                
            print(f"\n--- Evaluating Targets Inside: {folder} ---")
            images = [f for f in os.listdir(folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            for img_name in images[:8]:  
                img_path = os.path.join(folder, img_name)
                try:
                    raw_img = Image.open(img_path).convert('RGB')
                    tensor_img = transform(raw_img).unsqueeze(0).to(device)
                    
                    # FIX: Duplicate the tensor to create a batch of 2 
                    # This satisfies the f_all.chunk(2, dim=0) requirement
                    batch_input = torch.cat([tensor_img, tensor_img], dim=0)
                    
                    data_dict = {'image': batch_input} 
                    pred_dict = model(data_dict)
                    
                    # The model output usually returns logits for the whole batch.
                    # We take the result from the first index [0]
                    logits = pred_dict['cls']
                    probabilities = torch.softmax(logits, dim=1).cpu().numpy()[0]
                    
                    real_score = probabilities[0]
                    fake_score = probabilities[1]
                    prediction = "REAL" if real_score > fake_score else "FAKE"
                    
                    print(f"[{prediction}] {img_name} -> Real: {real_score:.4f} | Fake: {fake_score:.4f}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    print(f"[-] Execution issue skipping target image {img_name}: {str(e)}")

if __name__ == "__main__":
    run_native_ucf_pipeline()