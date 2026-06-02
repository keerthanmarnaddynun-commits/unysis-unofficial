#!/usr/bin/env python3
"""
audio_inference.py
CLI inference script for audio deepfake detection.
"""

import argparse
import json
import sys
from pathlib import Path

# Ensure the repository root is in the Python path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from audio_analysis.audio_detector import audio_predict

SUPPORTED_EXTS = {".wav", ".flac", ".mp3", ".m4a", ".ogg"}

def main():
    parser = argparse.ArgumentParser(description="Audio deepfake detection inference.")
    parser.add_argument("--input_path", required=True, help="Path to the input audio file")
    parser.add_argument("--output_json", help="Optional path to save full report as JSON")
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    
    if not input_path.exists():
        print(f"[!] Error: File not found: {input_path}")
        sys.exit(1)

    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_EXTS:
        print(f"[!] Warning: Unsupported or untested file type: {ext}. Proceeding anyway...")

    print(f"--- Audio Deepfake Detection ---")
    print(f"Input file: {input_path.name}")
    print("Running audio analysis...")
    
    try:
        result = audio_predict(str(input_path))
    except Exception as e:
        print(f"[!] Pipeline execution failed: {e}")
        sys.exit(1)

    if args.output_json:
        try:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=4)
            print(f"Full report saved to: {args.output_json}")
        except Exception as e:
            print(f"[!] Failed to save JSON report: {e}")

    print("\n" + "="*40)
    print("AUDIO ANALYSIS SUMMARY")
    print("="*40)
    
    if not result.get("available"):
        print("[!] Audio processing was unavailable or failed.")
    
    label = result.get("label", "Unknown")
    fake_prob = result.get("fake_prob", 0.5)
    note = result.get("note", "")

    print(f"Prediction: {label}")
    print(f"Fake Probability: {fake_prob:.4f}")
    if note:
        print(f"Note: {note}")
    print("="*40)

if __name__ == "__main__":
    main()
