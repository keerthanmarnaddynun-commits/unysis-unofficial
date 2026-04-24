import os
import json
import logging
import pandas as pd
import torch
from pathlib import Path
from sklearn.utils.class_weight import compute_class_weight
import numpy as np

def setup_logger(name, log_file, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    logger.addHandler(console_handler)
    
    return logger

def parse_metadata(metadata_path):
    """
    Automatically detects and parses JSON or CSV metadata.
    Returns a dictionary mapping video_filename -> label (0 for real, 1 for fake).
    """
    path = Path(metadata_path)
    if path.suffix == '.json':
        with open(path, 'r') as f:
            data = json.load(f)
            # DFDC json structure is usually {"video.mp4": {"label": "FAKE", ...}}
            return {k: 1 if v.get('label', '').upper() == 'FAKE' else 0 for k, v in data.items()}
    elif path.suffix == '.csv':
        df = pd.read_csv(path)
        # Assumes columns 'filename' and 'label'
        filename_col = 'filename' if 'filename' in df.columns else df.columns[0]
        label_col = 'label' if 'label' in df.columns else df.columns[1]
        
        def parse_label(lbl):
            if isinstance(lbl, str):
                return 1 if lbl.upper() == 'FAKE' else 0
            return int(lbl)
            
        return {row[filename_col]: parse_label(row[label_col]) for _, row in df.iterrows()}
    else:
        raise ValueError(f"Unsupported metadata format: {path.suffix}")

def calculate_class_weights(labels_list):
    """
    Computes class weights for imbalanced datasets.
    """
    if len(labels_list) == 0:
        return torch.tensor([1.0, 1.0], dtype=torch.float32)
        
    classes = np.unique(labels_list)
    if len(classes) < 2:
        # If only one class is present, default weights
        return torch.tensor([1.0, 1.0], dtype=torch.float32)
        
    weights = compute_class_weight('balanced', classes=classes, y=labels_list)
    return torch.tensor(weights, dtype=torch.float32)

def save_checkpoint(model, optimizer, epoch, is_best, checkpoint_dir):
    """
    Saves model checkpoint.
    """
    os.makedirs(checkpoint_dir, exist_ok=True)
    checkpoint_path = os.path.join(checkpoint_dir, f'checkpoint_epoch_{epoch}.pth')
    torch.save({
        'epoch': epoch,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict()
    }, checkpoint_path)
    
    if is_best:
        best_path = os.path.join(checkpoint_dir, 'best_model.pth')
        torch.save(model.state_dict(), best_path)
