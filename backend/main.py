"""
backend/main.py
───────────────
FastAPI rewrite of the BharatShield Deepfake Detection backend.
Migrates all Flask endpoints from the friend's app.py to FastAPI on port 5001.
"""

import os
import sys
import time
import uuid
import json
import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import FastAPI, File, UploadFile, HTTPException, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Ensure repo root is on sys.path
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import mps_patch
# ── Config ────────────────────────────────────────────────────
from config import (
    UPLOAD_FOLDER,
    MAX_FILE_SIZE_MB,
    ALLOWED_EXTENSIONS,
    SYSTEM_NAME,
    SYSTEM_VERSION,
    VIDEO_EXTENSIONS,
    IMAGE_EXTENSIONS,
    INFERENCE_TIMEOUT_S,
    AUDIT_LOG_FILE,
)

# ── Utils ─────────────────────────────────────────────────────
from modules.metadata_analysis.metadata import create_metadata
from modules.core.legal    import generate_legal_notice
from modules.metadata_analysis.hashing  import (
    compute_sha256,
    append_audit_entry,
    verify_audit_chain,
    generate_submission_id,
)
from pymongo import MongoClient
import certifi

# ── ML pipeline ───────────────────────────────────────────────
from modules.core.ensemble import run_detection

# Setup logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger("bharatshield_api")

app = FastAPI(
    title=SYSTEM_NAME,
    version=SYSTEM_VERSION,
    description="FastAPI Backend controlling ML pipeline and compliance audit layer",
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


async def save_upload(file: UploadFile) -> str:
    """Save uploaded file with collision-safe name. Returns abs path."""
    original = file.filename or "file"
    # Clean original filename
    original = "".join(c for c in original if c.isalnum() or c in "._-")
    unique_id = uuid.uuid4().hex[:8]
    filename = f"{unique_id}_{original}"
    path = os.path.join(UPLOAD_FOLDER, filename)
    
    # Write file in chunks to avoid memory issues
    with open(path, "wb") as f:
        while chunk := await file.read(65536):
            f.write(chunk)
            
    return path


async def _validate_file(file: UploadFile) -> None:
    """
    Validate the uploaded file object.
    Raises HTTPException on validation failure.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename.")

    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=415,
            detail=f"File type not allowed. Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Check size
    await file.seek(0, 2)
    size = await file.tell()
    await file.seek(0)

    if size == 0:
        raise HTTPException(status_code=400, detail="Empty file.")

    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max: {MAX_FILE_SIZE_MB}MB, received: {size / 1024 / 1024:.1f}MB"
        )


def _get_media_type(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "audio"


def _process_file(file_path: str) -> dict:
    """
    Full processing pipeline for a single file.
    Returns the complete structured response dict.
    """
    t_start = time.time()

    # ── Step 1: Generate submission ID + SHA-256 hash ─────────
    submission_id = generate_submission_id()
    file_hash     = compute_sha256(file_path)
    media_type    = _get_media_type(file_path)

    # ── Step 2: Audit log — RECEIVED ─────────────────────────
    append_audit_entry(
        submission_id = submission_id,
        file_hash     = file_hash,
        action        = "MEDIA_RECEIVED",
        actor         = "api_gateway",
        extra         = {"file": os.path.basename(file_path),
                         "media_type": media_type},
    )

    # ── Step 3: ML detection ──────────────────────────────────
    detection = run_detection(file_path, use_face_crop=True)

    result     = detection["label"]         # "Fake" | "Real"
    confidence = detection["confidence"]
    fake_prob  = detection["fake_prob"]
    risk_level = detection.get("risk_level", "MEDIUM")

    if media_type == "image" and result == "Fake":
        try:
            from modules.image_analysis.gradcam import generate_gradcam_secondary
            gradcam_path = os.path.join(UPLOAD_FOLDER, f"gradcam_{submission_id}.png")
            generate_gradcam_secondary(file_path, save_path=gradcam_path)
        except Exception as e:
            LOGGER.error("GradCAM auto-generation failed: %s", e)


    # ── Step 4: Audit log — DETECTION COMPLETE ────────────────
    append_audit_entry(
        submission_id = submission_id,
        file_hash     = file_hash,
        action        = "DETECTION_COMPLETE",
        actor         = "ml_pipeline",
        result        = {
            "label":      result,
            "confidence": confidence,
            "fake_prob":  fake_prob,
            "risk_level": risk_level,
        },
    )

    # ── Step 5: Fact-check pipeline (video/audio only) ────────
    fact_check_result = {"available": False,
                          "note": "Fact-check not run (image input)"}
    if media_type in ("video", "audio"):
        try:
            from modules.factcheck.pipeline import run_factcheck_pipeline
            fact_check_result = run_factcheck_pipeline(
                media_path = file_path,
                media_type = media_type,
            )
        except Exception as e:
            LOGGER.error("Fact-check pipeline error: %s", e)
            fact_check_result = {
                "available": False,
                "note":      f"Fact-check pipeline error: {str(e)}",
            }

    # ── Step 6: Build metadata ────────────────────────────────
    processing_ms = (time.time() - t_start) * 1000
    file_size     = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    def _size_human(b):
        for u in ["B", "KB", "MB", "GB"]:
            if b < 1024: return f"{b:.1f} {u}"
            b /= 1024
        return f"{b:.1f} TB"

    response = {
        "submission_id":  submission_id,
        "timestamp_utc":  datetime.now(timezone.utc).isoformat(),

        "file": {
            "name":       os.path.basename(file_path),
            "sha256":     file_hash,
            "media_type": media_type,
            "size_human": _size_human(file_size),
            "size_bytes": file_size,
        },

        "deepfake_detection": {
            "label":          result,
            "confidence":     round(confidence, 4),
            "risk_level":     risk_level,
            "is_deepfake":    result == "Fake",
            "fake_probability": round(fake_prob, 4),
            "streams":        detection.get("streams", {}),
            "metadata_flags": [],
            "gradcam_url":    f"/gradcam/{submission_id}"
                              if media_type == "image" else None,
            "processing_ms":  round(processing_ms, 1),
        },

        "fact_check": fact_check_result,

        "integrity": {
            "sha256":      file_hash,
            "audit_entry": f"BSA S.63 chain entry created (ID: {submission_id})",
        },
    }

    # ── Step 7: Legal report generation ───────────────────────
    try:
        from bharatshield_legal.legal2 import MediaEvidence, generate_all_documents
        
        evidence = MediaEvidence()
        evidence.case_id = submission_id
        evidence.media_filename = os.path.basename(file_path)
        evidence.media_sha256 = file_hash
        evidence.fusion_score = fake_prob
        evidence.verdict = "LIKELY SYNTHETIC" if fake_prob >= 0.50 else "LIKELY AUTHENTIC"
        evidence.model_version = "BharatShield-DetectCore v3.0 (Ensemble CBAM)"
        evidence.inference_duration = f"{processing_ms:.1f} ms"
        
        streams = detection.get("streams", {})
        evidence.cnn_score = streams.get("spatial_texture", {}).get("fake_prob", fake_prob)
        evidence.temporal_score = streams.get("temporal", {}).get("fake_prob", fake_prob)
        evidence.audio_score = streams.get("audio", {}).get("fake_prob", fake_prob)

        pdf_path = os.path.join(UPLOAD_FOLDER, f"BharatShield_Legal_{submission_id}.pdf")
        generate_all_documents(evidence=evidence, output_path=pdf_path)
        response["legal_report_url"] = f"/legal_report/{submission_id}"
    except Exception as e:
        LOGGER.error("Legal report generation failed: %s", e)
        response["legal_report_url"] = None
        response["legal_error"] = str(e)

    # ── Step 8: Audit log — REPORT GENERATED ─────────────────
    append_audit_entry(
        submission_id = submission_id,
        file_hash     = file_hash,
        action        = "REPORT_GENERATED",
        actor         = "compliance_layer",
        extra         = {
            "risk_level":       risk_level,
            "takedown_advised": risk_level == "HIGH",
            "fact_check_available": fact_check_result.get("available", False),
        },
    )

    return response


class LoginRequest(BaseModel):
    role: str
    identifier: str


@app.post("/verify-login")
async def verify_login(request: LoginRequest):
    mongo_uri = os.getenv("MONGO_URI")
    db_name = os.getenv("MONGO_DB", "unisys_project")
    
    if not mongo_uri:
        raise HTTPException(status_code=500, detail="Database configuration missing")
        
    try:
        client = MongoClient(mongo_uri, tlsCAFile=certifi.where())
        db = client[db_name]
        collection = db["authorized_ids"]
        
        role = request.role.strip().lower()
        identifier = request.identifier.strip()
        
        doc = collection.find_one({
            "role": role,
            "official_id": identifier,
            "status": "active"
        })
        
        if doc:
            return {
                "valid": True,
                "user": {
                    "role": doc.get("role"),
                    "official_id": doc.get("official_id"),
                    "name": doc.get("name"),
                    "organization": doc.get("organization")
                }
            }
        else:
            return {"valid": False, "message": "Invalid ID for selected role."}
    except Exception as exc:
        LOGGER.exception("Login verification failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database connection error")


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Liveness check."""
    return {
        "status": "ok",
        "service": SYSTEM_NAME,
        "version": SYSTEM_VERSION,
    }


@app.post("/analyze")
async def analyze_endpoint(file: UploadFile = File(...)):
    """
    Main endpoint for deepfake detection analysis.
    Accepts an uploaded file and processes it through the modular ensemble pipeline.
    """
    await _validate_file(file)
    file_path = await save_upload(file)

    try:
        response = _process_file(file_path)
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        LOGGER.error("Processing failed for /analyze: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


@app.post("/analyze/batch")
async def analyze_batch_endpoint(files: List[UploadFile] = File(...)):
    """
    Analyze multiple files in a single batch request (up to 10 files).
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 files per batch request.")

    results = []
    saved_paths = []

    # Validate and save all files first
    for file in files:
        try:
            await _validate_file(file)
            saved_path = await save_upload(file)
            saved_paths.append(saved_path)
            results.append(None)  # placeholder
        except HTTPException as he:
            results.append({"error": he.detail, "filename": file.filename})
            saved_paths.append(None)
        except Exception as e:
            results.append({"error": str(e), "filename": file.filename})
            saved_paths.append(None)

    # Process saved files
    for i, path in enumerate(saved_paths):
        if path is None:
            continue
        try:
            results[i] = _process_file(path)
        except Exception as e:
            LOGGER.error("Batch processing failed for %s: %s", files[i].filename, traceback.format_exc())
            results[i] = {
                "error": "Processing failed",
                "details": str(e),
                "filename": files[i].filename,
            }
        finally:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

    return {
        "batch_count": len(results),
        "results": results,
    }


@app.post("/gradcam")
async def gradcam_endpoint(file: UploadFile = File(...)):
    """
    Generate a Grad-CAM heatmap overlay for an image.
    """
    await _validate_file(file)

    # Grad-CAM only supports images
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(
            status_code=415,
            detail="Grad-CAM only supports image files (jpg, png, webp)."
        )

    file_path = await save_upload(file)
    heatmap_path = os.path.join(UPLOAD_FOLDER, f"gradcam_direct_{uuid.uuid4().hex[:8]}.png")

    try:
        from modules.image_analysis.gradcam import generate_gradcam_secondary
        generate_gradcam_secondary(file_path, save_path=heatmap_path)
        return FileResponse(heatmap_path, media_type="image/png")

    except Exception as e:
        LOGGER.error("Grad-CAM generation failed: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Grad-CAM failed: {str(e)}")

    finally:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass


@app.get("/audit/verify")
async def audit_verify_endpoint():
    """
    Verify the HMAC chain integrity of the audit log.
    """
    intact, message = verify_audit_chain()
    if not intact:
        raise HTTPException(status_code=409, detail=message)
    return {
        "intact": intact,
        "message": message,
    }


@app.get("/audit/log")
async def audit_log_endpoint(limit: int = Query(20, ge=1, le=200)):
    """
    Return the last N audit log entries (default 20).
    """
    if not os.path.exists(AUDIT_LOG_FILE):
        return {"entries": [], "total": 0}

    entries = []
    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

    return {
        "total": len(entries),
        "showing": min(limit, len(entries)),
        "entries": entries[-limit:],  # most recent first
    }


@app.get("/legal_report/{submission_id}")
async def get_legal_report(submission_id: str):
    """Download the generated PDF legal report."""
    pdf_path = os.path.join(UPLOAD_FOLDER, f"BharatShield_Legal_{submission_id}.pdf")
    if os.path.exists(pdf_path):
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=f"BharatShield_Legal_{submission_id}.pdf"
        )
    raise HTTPException(status_code=404, detail="Report not found or not generated")


@app.get("/gradcam/{submission_id}")
async def get_gradcam(submission_id: str):
    """Get the auto-generated GradCAM heatmap for an image."""
    path = os.path.join(UPLOAD_FOLDER, f"gradcam_{submission_id}.png")
    if os.path.exists(path):
        return FileResponse(path, media_type="image/png")
    raise HTTPException(status_code=404, detail="GradCAM not found or not generated")


# ── Entry point ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print(f"  {SYSTEM_NAME}")
    print(f"  Version: {SYSTEM_VERSION}")
    print("  Endpoints (FastAPI):")
    print("    POST /analyze          — single file detection")
    print("    POST /analyze/batch    — batch detection")
    print("    POST /gradcam          — heatmap overlay")
    print("    GET  /health           — liveness check")
    print("    GET  /audit/verify     — chain integrity check")
    print("    GET  /audit/log        — view audit entries")
    print("=" * 60)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=5001, reload=True)
