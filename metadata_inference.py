#!/usr/bin/env python3
"""
metadata_inference.py
CLI script for testing the metadata and hashing pipeline.
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure the repository root is in the Python path
_REPO_ROOT = Path(__file__).resolve().parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from metadata_analysis.metadata import create_metadata
from metadata_analysis.hashing import compute_sha256, generate_submission_id, append_audit_entry, verify_audit_chain

def main():
    parser = argparse.ArgumentParser(description="Metadata and hashing pipeline test script.")
    parser.add_argument("--input_path", required=False, help="Path to the input file")
    parser.add_argument("--label", choices=["Fake", "Real"], default="Fake", help="Detection label (Fake or Real)")
    parser.add_argument("--confidence", type=float, default=0.85, help="Confidence score [0, 1]")
    parser.add_argument("--time_ms", type=float, default=150.5, help="Processing time in ms (simulated inference time)")
    parser.add_argument("--output_json", help="Path to save the generated metadata JSON")
    parser.add_argument("--verify_chain", action="store_true", help="Verify the integrity of the audit log chain instead of creating metadata")
    
    args = parser.parse_args()

    if args.verify_chain:
        print("--- Verifying Audit Chain ---")
        is_valid, reason = verify_audit_chain()
        if is_valid:
            print(f"[+] SUCCESS: {reason}")
            sys.exit(0)
        else:
            print(f"[!] FAILED: {reason}")
            sys.exit(1)

    if not args.input_path:
        print("[!] Error: --input_path is required unless using --verify_chain")
        sys.exit(1)

    input_path = Path(args.input_path).expanduser().resolve()
    if not input_path.exists():
        print(f"[!] Error: File not found: {input_path}")
        sys.exit(1)

    print(f"--- Metadata Pipeline ---")
    print(f"Input file: {input_path.name}")
    print(f"Generating hashes and structured metadata...")

    # Start timing the metadata generation
    start_time = time.time()
    
    # 1. Hashing and ID generation
    file_hash = compute_sha256(str(input_path))
    submission_id = generate_submission_id()

    # 2. Append to audit log (tamper-evident chain)
    action = "DETECTION_COMPLETE"
    actor = "cli_user"
    
    # 3. Create metadata payload
    metadata = create_metadata(
        file_path=str(input_path),
        result=args.label,
        confidence=args.confidence,
        submission_id=submission_id,
        file_hash=file_hash,
        detection_detail={"example_model": {"prob": args.confidence}},
        processing_time_ms=args.time_ms
    )

    # 4. Log the result to the secure audit chain
    append_audit_entry(
        submission_id=submission_id,
        file_hash=file_hash,
        action=action,
        actor=actor,
        result={"label": args.label, "confidence": args.confidence},
    )

    processing_time = (time.time() - start_time) * 1000

    if args.output_json:
        try:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)
            print(f"Metadata saved to: {args.output_json}")
        except Exception as e:
            print(f"[!] Failed to save JSON metadata: {e}")

    print("\n" + "="*40)
    print("METADATA SUMMARY")
    print("="*40)
    print(f"Submission ID: {submission_id}")
    print(f"File SHA-256: {file_hash}")
    print(f"File Size: {metadata['file']['size_human']}")
    print(f"Media Type: {metadata['file']['media_type']}")
    print(f"Risk Level: {metadata['detection']['risk_level']}")
    print(f"Pipeline took {processing_time:.1f} ms to build metadata")
    print("="*40)

if __name__ == "__main__":
    main()
