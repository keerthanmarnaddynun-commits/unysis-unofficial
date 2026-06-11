# Metadata, Integrity & Tools Analysis

BharatShield emphasizes chain-of-custody and data integrity just as much as its machine learning detection capabilities. The `metadata_analysis` module ensures that every piece of media is cryptographically fingerprinted and logged in a tamper-evident manner.

## 1. Cryptographic Hashing & Audit Logs (`/metadata_analysis/hashing.py`)

This module implements a BSA (Bharatiya Sakshya Adhiniyam) compliant audit chain.

### Key Features:
- **File Hashing (`compute_sha256`)**: Instead of relying on vulnerable MD5 or reading the whole file into RAM, it computes a SHA-256 fingerprint by streaming the raw file bytes in 64KB chunks. This is critical for handling large videos efficiently.
- **Tamper-Evident HMAC Chain**: 
  - The system maintains a continuous, append-only JSONL audit log.
  - Every time an action occurs (e.g., "MEDIA_RECEIVED", "DETECTION_COMPLETE"), `append_audit_entry` is called.
  - It generates an HMAC-SHA256 signature that hashes the current event data **combined with the previous entry's HMAC**.
  - This creates a cryptographic blockchain-like structure. If a malicious actor alters a past log entry, it breaks the HMAC of all subsequent entries.
- **Verification (`verify_audit_chain`)**: A utility function that traverses the entire log file, recomputing and verifying the HMAC chain to prove to a court or authority that the logs have not been tampered with since creation.

---

## 2. Metadata API Payload (`/metadata_analysis/metadata.py`)

The `create_metadata` function acts as a serializer, transforming raw inference numbers into the rich, structured JSON payload consumed by the frontend.

### Output Structure:
- **Submission Info**: Assigns the unique `submission_id` and standardized UTC timestamps.
- **File Metadata**: Details the human-readable file size, extension type, and embeds the SHA-256 integrity hash.
- **Detection Result**: 
  - Translates the raw confidence score (e.g., `0.85`) into a human-readable `risk_level` (e.g., "CRITICAL", "HIGH", "LOW").
  - Formats a clear boolean `is_deepfake` flag.
- **Performance & Integrity**: Records the wall-clock processing time and asserts the chain-of-custody compliance statement.

---

## 3. Auxiliary Tools (`/tools`)

The `/tools` directory contains standalone scripts used by the developers to maintain the integrity of the underlying datasets used to train the ML models.

### Dataset Audit (`dataset_audit.py`)
This script audits a deepfake dataset (e.g., a custom compiled dataset on the developer's local `D:/forsen` drive) before training.
- **Class Balance**: Counts real vs. fake images across `train`, `val`, and `test` splits.
- **Duplicate Detection**: Uses **dHash** (Difference Hash) to find near-duplicate images within the dataset to prevent data leakage between training and validation sets.
- **Image Metrics**: Calculates aggregate statistics using OpenCV:
  - Lighting (mean and standard deviation of grayscale pixels)
  - Blur levels (variance of the Laplacian)
  - Face detection counts (identifying images with 0 faces or multiple faces, which could break single-face cropping assumptions).
- **Report**: Outputs all findings to a `dataset_audit_report.json` file.
