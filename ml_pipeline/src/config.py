import os
import torch

# Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
METADATA_DIR = os.path.join(DATA_DIR, 'metadata')
CHECKPOINT_DIR = os.path.join(BASE_DIR, 'models', 'checkpoints')

# Preprocessing Settings
FPS_EXTRACTION = 1
FACE_MARGIN = 20 # margin to add around detected face
IMAGE_SIZE = (224, 224) # standard for EfficientNet/ResNet

# Training Hyperparameters
BATCH_SIZE = 32  #32
NUM_EPOCHS = 10  #10
LEARNING_RATE = 1e-4

# Device Configuration
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
