#!/bin/bash
# Description: Script to start the deepfake training pipeline.
# Run this from the ml_pipeline root directory.

echo "Starting Deepfake Model Training..."
python src/train.py
echo "Training pipeline finished."
