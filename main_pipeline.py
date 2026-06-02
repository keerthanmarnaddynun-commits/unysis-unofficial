#!/usr/bin/env python3
"""
main_pipeline.py
Unified Multimodal Deepfake Detection Pipeline.
Upgraded to use the new modular ensemble and factcheck pipeline.
"""

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

# Ensure repo root is in python path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Imports from Modular Ensemble ────────────────────────────────────
from modules.metadata_analysis.metadata import create_metadata
from modules.metadata_analysis.hashing import (
    compute_sha256,
    generate_submission_id,
    append_audit_entry,
)
from modules.core.ensemble import run_detection
from modules.audio_analysis.audio_detector import audio_predict
from modules.factcheck.pipeline import run_factcheck_pipeline

# Allowed types
from config import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS, AUDIO_EXTENSIONS


def main():
    parser = argparse.ArgumentParser(description="Main Multimodal Pipeline for Deepfake Detection")
    parser.add_argument("--input_path", required=True, help="Path to input media (Image/Video/Audio)")
    parser.add_argument("--output_json", help="Path to output metadata JSON", default="final_report.json")
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        print(f"[!] Error: File not found: {input_path}")
        sys.exit(1)

    ext = input_path.suffix.lower()
    media_type = "unknown"
    if ext in IMAGE_EXTENSIONS:
        media_type = "image"
    elif ext in VIDEO_EXTENSIONS:
        media_type = "video"
    elif ext in AUDIO_EXTENSIONS:
        media_type = "audio"
    else:
        print(f"[!] Error: Unsupported file extension {ext}")
        sys.exit(1)

    print(f"--- BharatShield Unified CLI Pipeline ---")
    print(f"File: {input_path.name}")
    print(f"Type: {media_type.upper()}")
    print("Running modular detection pipeline...")

    start_time = time.time()
    
    # ── 1. Hashing & Identity ──
    file_hash = compute_sha256(str(input_path))
    sub_id = generate_submission_id()
    
    overall_confidence = 0.0
    overall_result = "Real"
    detection_detail = {}
    factcheck_res = {"available": False, "note": "Fact-check not run."}

    # Append initial audit entry
    append_audit_entry(
        submission_id=sub_id,
        file_hash=file_hash,
        action="MEDIA_RECEIVED",
        actor="main_pipeline",
        extra={"file": input_path.name, "media_type": media_type},
    )

    # ── 2. Run Modular Inference ──
    if media_type in ("image", "video"):
        detection = run_detection(str(input_path), use_face_crop=True)
        
        overall_result = detection["label"]
        overall_confidence = detection["confidence"]
        
        detection_detail = {
            "is_deepfake": detection["is_deepfake"],
            "risk_level": detection["risk_level"],
            "fake_probability": detection["fake_prob"],
            "streams": detection["streams"],
        }
        
        # Run factcheck for videos
        if media_type == "video":
            try:
                print("Running factcheck pipeline...")
                factcheck_res = run_factcheck_pipeline(str(input_path), media_type="video")
            except Exception as e:
                print(f"[!] Fact-check failed: {e}")
                factcheck_res = {"available": False, "note": f"Error: {e}"}

    elif media_type == "audio":
        audio_res = audio_predict(str(input_path))
        
        overall_result = audio_res.get("label", "Unknown")
        fake_prob = audio_res.get("fake_prob", 0.5)
        overall_confidence = fake_prob if overall_result == "Fake" else (1.0 - fake_prob)
        
        detection_detail = {
            "audio": {
                "fake_prob": fake_prob,
                "note": audio_res.get("note", "")
            }
        }
        
        try:
            print("Running factcheck pipeline...")
            factcheck_res = run_factcheck_pipeline(str(input_path), media_type="audio")
        except Exception as e:
            print(f"[!] Fact-check failed: {e}")
            factcheck_res = {"available": False, "note": f"Error: {e}"}

    processing_time_ms = (time.time() - start_time) * 1000

    # ── 3. Build Metadata & Log ──
    metadata = create_metadata(
        file_path=str(input_path),
        result=overall_result,
        confidence=overall_confidence,
        submission_id=sub_id,
        file_hash=file_hash,
        detection_detail=detection_detail,
        processing_time_ms=processing_time_ms
    )
    metadata["fact_check"] = factcheck_res

    # Append completion audit entry
    append_audit_entry(
        submission_id=sub_id,
        file_hash=file_hash,
        action="DETECTION_COMPLETE",
        actor="main_pipeline",
        result={"label": overall_result, "confidence": overall_confidence}
    )

    if args.output_json:
        try:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)
            print(f"\n[+] Full report saved to: {args.output_json}")
        except Exception as e:
            print(f"[!] Failed to save JSON report: {e}")

    print("\n" + "="*50)
    print("UNIFIED DEEPFAKE DETECTION SUMMARY")
    print("="*50)
    print(f"Submission ID: {sub_id}")
    print(f"Media Type:    {metadata['file']['media_type'].upper()}")
    print(f"Final Label:   {metadata['detection']['label']}")
    print(f"Confidence:    {metadata['detection']['confidence']:.4f}")
    print(f"Risk Level:    {metadata['detection']['risk_level']}")
    
    if factcheck_res.get("available"):
        print(f"Misinfo Risk:  {factcheck_res.get('overall_misinfo_risk', 'UNKNOWN')}")
        claims = factcheck_res.get("claims", [])
        if claims:
            print(f"Claims Found:  {len(claims)}")

    print(f"Process Time:  {metadata['processing']['time_ms']} ms")
    print("="*50)


if __name__ == "__main__":
    main()
