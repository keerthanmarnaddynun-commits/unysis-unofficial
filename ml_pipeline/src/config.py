import os
import torch

# Base Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
RAW_DATA_DIR = os.path.join(DATA_DIR, 'raw')
PROCESSED_DATA_DIR = os.path.join(DATA_DIR, 'processed')
METADATA_DIR = os.path.join(DATA_DIR, 'metadata')
CHECKPOINT_DIR = os.path.join(BASE_DIR, 'models', 'checkpoints')

# New balanced folder-based dataset
_PREFERRED_DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'dataset'))
_FALLBACK_DATASET_DIR = os.path.abspath(os.path.join(BASE_DIR, '..', 'base_deepfake'))
DATASET_BASE_DIR = _PREFERRED_DATASET_DIR if os.path.isdir(_PREFERRED_DATASET_DIR) else _FALLBACK_DATASET_DIR
TRAIN_DIR = os.path.join(DATASET_BASE_DIR, 'train')
VAL_DIR = os.path.join(DATASET_BASE_DIR, 'val')
TEST_DIR = os.path.join(DATASET_BASE_DIR, 'test')

# Preprocessing Settings
FPS_EXTRACTION = 1
FACE_MARGIN = 20 # margin to add around detected face
IMAGE_SIZE = (224, 224) # standard for EfficientNet/ResNet

# Training Hyperparameters
BATCH_SIZE = 32  #32
NUM_EPOCHS = 12
LEARNING_RATE = 2e-4
VAL_SPLIT_RATIO = 0.12
RANDOM_SEED = 42
HEAD_DROPOUT = 0.3

# Device Configuration
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
