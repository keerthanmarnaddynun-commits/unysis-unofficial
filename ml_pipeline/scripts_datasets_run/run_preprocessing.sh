#!/bin/bash
# Description: Script to run face extraction from raw videos.
# Run this from the ml_pipeline root directory.

echo "Starting Face Extraction Preprocessing..."
python src/face_extractor.py
echo "Preprocessing complete."
