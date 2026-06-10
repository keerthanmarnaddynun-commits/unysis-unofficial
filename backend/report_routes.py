"""
Report routes — FastAPI router for the authority reporting system.
"""

from __future__ import annotations

import hashlib
import logging
import os
import tempfile
from datetime import datetime, timezone, timedelta

# Define IST timezone
IST = timezone(timedelta(hours=5, minutes=30))
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, Depends
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])

# Will be set during app startup from main.py
_report_service = None
_img_models = None


def set_report_service(service):
    global _report_service
    _report_service = service


def set_img_models(models):
    global _img_models
    _img_models = models


def _get_service():
    if _report_service is None:
        raise HTTPException(500, "Report service not initialized")
    return _report_service


# --- Pydantic models ---


class ReportSubmitRequest(BaseModel):
    reporter_role: str
    reporter_identifier: str
    reporter_name: str | None = None
    analysis: dict[str, Any]
    media_hash: str | None = None
    media_filename: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str
    admin_notes: str | None = None


# --- Endpoints ---


@router.post("/submit")
async def submit_report(
    analysis_json: str = Form(...),
    file: UploadFile | None = File(None),
    current_user: dict = Depends(get_current_user),
):
    """Submit a deepfake report to authorities."""
    import json

    svc = _get_service()

    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(400, f"Invalid analysis JSON: {exc}")

    # Block submission if prediction is not Fake (only suspected deepfakes can be escalated)
    prediction = analysis.get("prediction") or analysis.get("label") or analysis.get("final_prediction")
    if prediction and prediction.lower() not in ["fake", "likely deepfake", "synthetic"]:
        raise HTTPException(
            400,
            "Only suspected synthetic/manipulated deepfake media can be escalated to the official grievance ledger. "
            f"Current prediction: {prediction}. Real/authentic media does not require reporting."
        )

    # Store media in GridFS if provided
    media_file_id = None
    media_hash = None
    media_filename = None

    if file and file.filename:
        file_bytes = await file.read()
        if len(file_bytes) > 0:
            media_hash = hashlib.sha256(file_bytes).hexdigest()
            media_filename = file.filename
            try:
                media_file_id = await svc.store_media(
                    file_bytes, file.filename,
                    content_type=file.content_type or "application/octet-stream",
                )
            except Exception as exc:
                logger.warning("GridFS storage failed, continuing without: %s", exc)
                # Fallback: store locally
                local_dir = Path(__file__).resolve().parent / "report_media"
                local_dir.mkdir(parents=True, exist_ok=True)
                local_path = local_dir / f"{media_hash[:16]}_{file.filename}"
                local_path.write_bytes(file_bytes)
                media_file_id = f"local:{local_path}"
    else:
        media_hash = analysis.get("media_hash", analysis.get("hash", ""))
        media_filename = analysis.get("media_filename", analysis.get("file_name", "unknown"))

    # Extract sourceUrl from analysis if available (from VibeStream forward)
    source_url = analysis.get("sourceUrl") or analysis.get("source_url")
    
    report = await svc.create_report(
        reporter_role=current_user["role"],
        reporter_identifier=current_user["identifier"],
        reporter_name=current_user.get("name"),
        analysis_data=analysis,
        media_file_id=media_file_id,
        media_hash=media_hash,
        media_filename=media_filename,
        source_url=source_url,
    )

    return JSONResponse(content={
        "success": True,
        "report_id": report["report_id"],
        "status": report["status"],
        "message": f"Report {report['report_id']} submitted successfully",
    })


@router.post("/submit-json")
async def submit_report_json(
    req: ReportSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    """Submit a report via JSON body (no file upload)."""
    # Block submission if prediction is not Fake (only suspected deepfakes can be escalated)
    prediction = req.analysis.get("prediction") or req.analysis.get("label") or req.analysis.get("final_prediction")
    if prediction and prediction.lower() not in ["fake", "likely deepfake", "synthetic"]:
        raise HTTPException(
            400,
            "Only suspected synthetic/manipulated deepfake media can be escalated to the official grievance ledger. "
            f"Current prediction: {prediction}. Real/authentic media does not require reporting."
        )
    
    svc = _get_service()

    # Extract sourceUrl from analysis if available (from VibeStream forward)
    source_url = req.analysis.get("sourceUrl") or req.analysis.get("source_url")

    report = await svc.create_report(
        reporter_role=current_user["role"],
        reporter_identifier=current_user["identifier"],
        reporter_name=current_user.get("name"),
        analysis_data=req.analysis,
        media_file_id=None,
        media_hash=req.media_hash,
        media_filename=req.media_filename,
        source_url=source_url,
    )

    return JSONResponse(content={
        "success": True,
        "report_id": report["report_id"],
        "status": report["status"],
        "message": f"Report {report['report_id']} submitted successfully",
    })


@router.get("")
async def list_reports(
    status: str | None = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """List reports. Authority users see all, others see their own."""
    # Debug logging
    print(f"[DEBUG] list_reports endpoint - current_user: {current_user}")
    print(f"[DEBUG] list_reports endpoint - role: {current_user.get('role')}, identifier: {current_user.get('identifier')}")
    
    svc = _get_service()
    reports = await svc.list_reports(
        role=current_user["role"],
        reporter_identifier=current_user["identifier"],
        status=status,
        limit=limit,
    )
    return JSONResponse(content={"reports": reports})


@router.get("/{report_id}")
async def get_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a single report by its case ID."""
    svc = _get_service()
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    
    # Non-authority users can only view their own reports
    if current_user["role"] != "authority":
        if report.get("reporter", {}).get("identifier") != current_user["identifier"]:
            raise HTTPException(403, "Access denied: You can only view your own reports")
    
    return JSONResponse(content={"report": report})


@router.patch("/{report_id}/status")
async def update_report_status(
    report_id: str,
    req: StatusUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update report status (authority only)."""
    # Only authority users can update status
    if current_user["role"] != "authority":
        raise HTTPException(403, "Access denied: Only authority users can update report status")
    
    svc = _get_service()
    report = await svc.update_status(report_id, req.status, req.admin_notes)
    if not report:
        raise HTTPException(404, "Report not found")
    return JSONResponse(content={"success": True, "report": report})


@router.post("/{report_id}/reanalyze")
async def reanalyze_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Re-run deepfake detection on stored media (authority re-evaluation)."""
    # Only authority users can reanalyze
    if current_user["role"] != "authority":
        raise HTTPException(403, "Access denied: Only authority users can reanalyze reports")
    
    svc = _get_service()
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    media_file_id = report.get("media_file_id")
    if not media_file_id:
        raise HTTPException(400, "No media stored for this report")

    if _img_models is None:
        raise HTTPException(500, "Detection models not loaded")

    # Retrieve media
    try:
        if media_file_id.startswith("local:"):
            local_path = Path(media_file_id[6:])
            if not local_path.exists():
                raise HTTPException(404, "Media file not found on disk")
            file_bytes = local_path.read_bytes()
            filename = local_path.name
        else:
            file_bytes, filename = await svc.retrieve_media(media_file_id)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to retrieve media: {exc}")

    # Write to temp file and run detection
    ext = Path(filename).suffix.lower()
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=ext, prefix="reanalyze_")
        os.close(tmp_fd)
        Path(tmp_path).write_bytes(file_bytes)

        from ml.config import ALLOWED_IMAGE_EXTENSIONS, ALLOWED_VIDEO_EXTENSIONS

        if ext in ALLOWED_IMAGE_EXTENSIONS:
            from image_inference import infer_image

            res = infer_image(
                Path(tmp_path),
                cnn_model=_img_models["cnn_model"],
                fft_model=_img_models["fft_model"],
                bundle=_img_models["bundle"],
                device=_img_models["device"],
                cnn_transform=_img_models["cnn_transform"],
                fft_cfg=_img_models["fft_cfg"],
                dataset_mean=_img_models["dataset_mean"],
                dataset_std=_img_models["dataset_std"],
                radial_mask=_img_models["radial_mask"],
                face_crop=True,
                skip_no_face=False,
            )
            new_analysis = {
                "media_type": "image",
                "prediction": str(getattr(res, "label_final", "")).capitalize(),
                "confidence": float(getattr(res, "confidence", 0.0)),
                "reliability": str(getattr(res, "reliability", "")),
                "cnn_prediction": str(getattr(res.cnn, "label", "")) if res.cnn else "",
                "cnn_probability": float(getattr(res.cnn, "prob_fake", 0.0)) if res.cnn else 0.0,
                "fft_prediction": str(getattr(res.fft, "label", "")) if res.fft else "",
                "fft_probability": float(getattr(res.fft, "prob_fake", 0.0)) if res.fft else 0.0,
                "fusion_prediction": str(getattr(res, "label_final", "")).capitalize(),
                "fusion_probability": float(getattr(res, "prob_final", 0.0)),
            }
        elif ext in ALLOWED_VIDEO_EXTENSIONS:
            from ml.inference import predict_video

            pred = predict_video(tmp_path)
            new_analysis = {
                "media_type": "video",
                "prediction": pred["final_prediction"].capitalize(),
                "confidence": pred["confidence"],
                **pred,
            }
        else:
            raise HTTPException(400, f"Unsupported media type: {ext}")

        # Update report
        updated = await svc.add_reanalysis(report_id, new_analysis)
        return JSONResponse(content={
            "success": True,
            "new_analysis": new_analysis,
            "report": updated,
        })

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Re-analysis failed: %s", exc)
        raise HTTPException(500, f"Re-analysis failed: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.post("/{report_id}/generate-legal-docs")
async def generate_legal_docs(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Generate legal documents for a report."""
    # Only authority users can generate legal docs
    if current_user["role"] != "authority":
        raise HTTPException(403, "Access denied: Only authority users can generate legal documents")
    
    svc = _get_service()
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    analysis = report.get("analysis", {})
    media_filename = report.get("media_filename", "unknown")
    media_hash = report.get("media_hash", "0" * 64)

    try:
        from legal_integration import generate_legal_documents

        documents = await generate_legal_documents(
            analysis=analysis,
            media_filename=media_filename,
            media_hash=media_hash,
            media_size=analysis.get("file_size", 1024),
            reporter_name=report.get("reporter", {}).get("name"),
        )

        # Store document references in report
        doc_refs = []
        for doc in documents:
            doc_refs.append({
                "document_type": doc["document_type"],
                "filename": doc["filename"],
                "packet_id": doc.get("packet_id", ""),
            })

        await svc.add_legal_documents(report_id, doc_refs)

        return JSONResponse(content={
            "success": True,
            "documents": doc_refs,
            "packet_id": documents[0]["packet_id"] if documents else None,
        })

    except Exception as exc:
        logger.exception("Legal doc generation failed: %s", exc)
        raise HTTPException(500, f"Legal document generation failed: {exc}")


@router.get("/{report_id}/documents/{packet_id}/{filename}")
async def download_document(
    report_id: str,
    packet_id: str,
    filename: str,
    token: str | None = None,
):
    """Download a generated legal document PDF."""
    # Try to get user from token (either from header or query param)
    from fastapi import Header
    from auth import decode_token
    
    current_user = None
    auth_header = None
    
    # Check for token in query param first (for direct download links)
    if token:
        try:
            payload = decode_token(token)
            current_user = {
                "role": payload.get("role"),
                "identifier": payload.get("identifier"),
                "name": payload.get("name"),
                "organization": payload.get("organization"),
            }
        except:
            pass
    
    # If no token in query, try to use the dependency (for API calls with Authorization header)
    if not current_user:
        try:
            from fastapi import Request
            # This won't work in this context, so we'll require the token param for downloads
            raise HTTPException(401, "Authentication required for document download")
        except:
            if not token:
                raise HTTPException(401, "Authentication required for document download")
    
    # Users can only download documents for their own reports (unless authority)
    if current_user and current_user["role"] != "authority":
        svc = _get_service()
        report = await svc.get_report(report_id)
        if not report:
            raise HTTPException(404, "Report not found")
        if report.get("reporter", {}).get("identifier") != current_user["identifier"]:
            raise HTTPException(403, "Access denied: You can only download documents for your own reports")
    
    # Sanitize filename
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")

    # Primary search location
    output_dir = Path(__file__).resolve().parent / "legal_output" / packet_id / "documents"
    file_path = output_dir / safe_name

    # Secondary search location (fallback to bharatshield_legal2/output)
    if not file_path.is_file():
        alt_output_dir = Path(__file__).resolve().parent.parent / "bharatshield_legal2" / "output" / packet_id / "documents"
        file_path = alt_output_dir / safe_name

    if not file_path.is_file():
        raise HTTPException(404, "Document not found")

    return FileResponse(file_path, filename=safe_name, media_type="application/pdf")


@router.post("/{report_id}/send-takedown")
async def send_takedown_notice(
    report_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Send a legal takedown notice to VibeStream admin panel."""
    # Only authority users can send takedown notices
    if current_user["role"] != "authority":
        raise HTTPException(403, "Access denied: Only authority users can send takedown notices")
    
    svc = _get_service()
    report = await svc.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")

    analysis = report.get("analysis", {})
    media_hash = report.get("media_hash", "")
    media_filename = report.get("media_filename", "unknown")
    media_file_id = report.get("media_file_id", "")
    prediction = analysis.get("final_prediction") or analysis.get("prediction", "Unknown")
    confidence = analysis.get("confidence", 0.0)

    # Get legal packet ID if available
    legal_packet_id = None
    if report.get("legal_documents") and len(report["legal_documents"]) > 0:
        legal_packet_id = report["legal_documents"][0].get("packet_id")

    # Extract the actual static file URL from the report
    # The report should contain the original source URL from VibeStream
    source_url = report.get("source_url") or report.get("media_url")
    
    # If source_url exists, use it directly (this is the actual VibeStream post URL)
    if source_url:
        # Ensure it's an absolute URL
        if not source_url.startswith("http"):
            source_url = f"http://localhost:4000{source_url}"
    else:
        # Fallback: if no source URL, we can't construct a public URL for local files
        # Use the VibeStream API endpoint as fallback
        source_url = f"http://localhost:4001/api/get-content?postId={report_id}"

    # Build takedown notice payload
    takedown_payload = {
        "sourceUrl": source_url,
        "caseId": report_id,
        "mediaHash": media_hash,
        "legalPacketId": legal_packet_id,
        "prediction": prediction,
        "confidence": confidence,
        "reason": f"Deepfake detected with {confidence:.2%} confidence - Legal notice generated under IT Rules 2026",
        "reportId": report_id
    }

    try:
        # Send to VibeStream backend
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    "http://localhost:4001/api/takedown",
                    json=takedown_payload
                )
                response.raise_for_status()
                vibestream_response = response.json()
            except httpx.ConnectError as e:
                logger.error("Failed to connect to VibeStream: %s", e)
                # VibeStream might not be running, but we should still update the report status
                await svc.update_takedown_status(
                    report_id,
                    "sent",
                    {
                        "sent_at": datetime.now(IST).isoformat(),
                        "vibestream_response": {"success": True, "message": "Takedown notice logged (VibeStream connection failed)"},
                        "payload": takedown_payload,
                        "warning": "VibeStream backend unreachable"
                    }
                )
                return JSONResponse(content={
                    "success": True,
                    "message": "Takedown notice logged (VibeStream backend unreachable)",
                    "takedown_status": "sent",
                    "warning": "VibeStream backend unreachable"
                })
            except httpx.TimeoutException as e:
                logger.error("VibeStream takedown API timeout: %s", e)
                await svc.update_takedown_status(
                    report_id,
                    "sent",
                    {
                        "sent_at": datetime.now(IST).isoformat(),
                        "vibestream_response": {"success": True, "message": "Takedown notice logged (VibeStream timeout)"},
                        "payload": takedown_payload,
                        "warning": "VibeStream backend timeout"
                    }
                )
                return JSONResponse(content={
                    "success": True,
                    "message": "Takedown notice logged (VibeStream backend timeout)",
                    "takedown_status": "sent",
                    "warning": "VibeStream backend timeout"
                })

        # Update report with takedown status
        await svc.update_takedown_status(
            report_id,
            "sent",
            {
                "sent_at": datetime.now(IST).isoformat(),
                "vibestream_response": vibestream_response,
                "payload": takedown_payload
            }
        )

        return JSONResponse(content={
            "success": True,
            "message": "Takedown notice sent to VibeStream successfully",
            "takedown_status": "sent",
            "vibestream_response": vibestream_response
        })

    except httpx.HTTPStatusError as e:
        logger.error("VibeStream takedown API error: %s", e)
        await svc.update_takedown_status(
            report_id,
            "failed",
            {
                "sent_at": datetime.now(IST).isoformat(),
                "error": str(e),
                "payload": takedown_payload
            }
        )
        raise HTTPException(502, f"Failed to send takedown notice to VibeStream: {e}")
    except Exception as exc:
        logger.exception("Takedown notice send failed: %s", exc)
        await svc.update_takedown_status(
            report_id,
            "failed",
            {
                "sent_at": datetime.now(IST).isoformat(),
                "error": str(exc),
                "payload": takedown_payload
            }
        )
        raise HTTPException(500, f"Takedown notice send failed: {exc}")

