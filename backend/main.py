import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))



from ml.config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_IMAGE_SIZE_MB,
    MAX_VIDEO_SIZE_MB,
    UPLOAD_DIR,
    setup_logging,
)
from factcheck.pipeline import run_factcheck_pipeline
from utils.legal import generate_legal_notice
from utils.metadata import create_metadata
from pymongo import MongoClient
import certifi
from pydantic import BaseModel

from report_service import ReportService
from report_routes import router as report_router, set_report_service, set_img_models
from auth import create_access_token


from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

setup_logging()
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="BharatShield Backend", version="1.0.0")
# Enable CORS for local development - include both localhost and 127.0.0.1 variants
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:4000",  # VibeStream platform port
        "http://127.0.0.1:4000",  # VibeStream platform port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(report_router)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
EVIDENCE_DIR = _REPO_ROOT / "backend" / "video_evidence_frames"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(EVIDENCE_DIR)), name="evidence")

# Report service singleton
_report_service = ReportService()

MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
MAX_VIDEO_SIZE_BYTES = MAX_VIDEO_SIZE_MB * 1024 * 1024


def _validate_extension(filename: str, allowed_set) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in allowed_set:
        raise HTTPException(status_code=400, detail="Unsupported file type")


async def _read_upload_with_limit(upload: UploadFile, max_size_bytes: int) -> bytes:
    data = await upload.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(data) > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size: {max_size_bytes // 1024 // 1024}MB")
    return data


def _write_temp_file(content: bytes, suffix: str) -> str:
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=str(UPLOAD_DIR))
    tmp_file.write(content)
    tmp_file.flush()
    tmp_file.close()
    return tmp_file.name


IMG_MODELS = {}

@app.on_event("startup")
async def startup_event() -> None:
    from datetime import datetime
    print(f"[{datetime.now()}] [STARTUP BEGIN]")
    print("VERIFY_LOGIN_USING_SHARED_REPORT_SERVICE_DB_FIX_ACTIVE")
    LOGGER.info("VERIFY_LOGIN_USING_SHARED_REPORT_SERVICE_DB_FIX_ACTIVE")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR = _REPO_ROOT / "backend" / "video_evidence_frames"
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    # Initialize report service with MongoDB
    try:
        await _report_service.init()
        set_report_service(_report_service)
        set_img_models(IMG_MODELS)
        LOGGER.info("Report service initialized successfully")
    except Exception as exc:
        LOGGER.warning("Report service init failed (reports disabled): %s", exc)

    print(f"[{datetime.now()}] [STARTUP END]")

@app.on_event("shutdown")
async def shutdown_event() -> None:
    await _report_service.close()

def get_img_models():
    global IMG_MODELS
    if IMG_MODELS:
        return IMG_MODELS
        
    from datetime import datetime
    print(f"[{datetime.now()}] [MODEL LOAD BEGIN]")
    from image_inference import (
        resolve_device, load_cnn_model, load_fft_checkpoint, load_fusion_bundle,
        get_transform, load_fft_run_config, load_stats, build_radial_emphasis_mask,
        DEFAULT_CNN_MODEL, DEFAULT_FFT_MODEL, DEFAULT_FUSION_BUNDLE, DEFAULT_FFT_RUN_CONFIG, DEFAULT_FFT_STATS
    )
    import torch
    device = resolve_device(None)
    if device.type == "cuda":
        try:
            _ = torch.zeros(1, device=device).matmul(torch.zeros(1, device=device))
        except Exception:
            pass
    cnn_model, _ = load_cnn_model(Path(DEFAULT_CNN_MODEL), device)
    fft_model, _ = load_fft_checkpoint(Path(DEFAULT_FFT_MODEL), device)
    bundle = load_fusion_bundle(Path(DEFAULT_FUSION_BUNDLE))
    cnn_transform = get_transform()
    fft_cfg = load_fft_run_config(Path(DEFAULT_FFT_RUN_CONFIG))
    dataset_mean, dataset_std = None, None
    if fft_cfg.norm_mode == "dataset" and fft_cfg.stats_file.is_file():
        dataset_mean, dataset_std = load_stats(fft_cfg.stats_file)
    radial_mask = None
    if fft_cfg.radial_emphasis:
        radial_mask = build_radial_emphasis_mask(fft_cfg.image_size, fft_cfg.radial_emphasis_sigma)
        
    IMG_MODELS.update({
        "device": device,
        "cnn_model": cnn_model,
        "fft_model": fft_model,
        "bundle": bundle,
        "cnn_transform": cnn_transform,
        "fft_cfg": fft_cfg,
        "dataset_mean": dataset_mean,
        "dataset_std": dataset_std,
        "radial_mask": radial_mask,
    })
    print(f"[{datetime.now()}] [MODEL LOAD END]")
    return IMG_MODELS

class LoginRequest(BaseModel):
    role: str
    identifier: str

@app.post("/verify-login")
async def verify_login(request: LoginRequest):
    LOGGER.info("verify_login: id(_report_service) = %s", id(_report_service))
    LOGGER.info("verify_login: _report_service._db is None? %s", getattr(_report_service, "_db", None) is None)
    
    db = getattr(_report_service, "_db", None)
    if db is None:
        try:
            await _report_service.init()
            db = getattr(_report_service, "_db", None)
        except Exception as exc:
            LOGGER.warning("Dynamic initialization of ReportService failed on login request: %s", exc)
            
    if db is None:
        LOGGER.error("Database configuration missing: ReportService db client is not initialized")
        raise HTTPException(status_code=500, detail="Database configuration missing")
        
    LOGGER.info("verify_login: db.name = %s", db.name)
    
    try:
        role = request.role.strip().lower()
        identifier = request.identifier.strip()
        
        collection = db["authorized_ids"]
        
        # Check if the database has any documents in the authorized_ids collection to fail gracefully with logs
        count = await collection.count_documents({})
        LOGGER.info("verify_login: authorized_ids count = %s", count)
        if count == 0:
            LOGGER.warning("authorized_ids collection is empty or missing in database")
            
        doc = await collection.find_one({
            "role": role,
            "$or": [
                {"official_id": identifier},
                {"identifier": identifier},
                {"id": identifier}
            ],
            "status": "active"
        })
        
        LOGGER.info("verify_login: lookup result found: %s", doc is not None)
        
        if doc:
            # Create JWT token
            official_id = doc.get("official_id") or doc.get("identifier") or doc.get("id") or identifier
            access_token = create_access_token(data={
                "role": doc.get("role"),
                "identifier": official_id,
                "name": doc.get("name"),
                "organization": doc.get("organization")
            })
            
            return {
                "valid": True,
                "access_token": access_token,
                "token_type": "bearer",
                "user": {
                    "role": doc.get("role"),
                    "official_id": official_id,
                    "name": doc.get("name"),
                    "organization": doc.get("organization")
                }
            }
        else:
            LOGGER.warning("Login failed: active user with identifier '%s' and role '%s' not found", identifier, role)
            return {"valid": False, "message": "Invalid ID for selected role."}
            
    except Exception as exc:
        LOGGER.exception("Login verification query failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database connection error")


@app.post("/predict/video")
async def predict_video_endpoint(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    _validate_extension(file.filename, ALLOWED_VIDEO_EXTENSIONS)

    if os.getenv("SMOKE_TEST_MODE", "").lower() == "true":
        LOGGER.info("SMOKE_TEST_MODE active: Returning mock video prediction result")
        return JSONResponse(content={
            "final_prediction": "fake",
            "confidence": 0.88,
            "frames_analyzed": 5,
            "frame_predictions": [
                {"frame_index": 0, "prediction": "fake", "confidence": 0.85},
                {"frame_index": 1, "prediction": "fake", "confidence": 0.90},
                {"frame_index": 2, "prediction": "fake", "confidence": 0.88},
                {"frame_index": 3, "prediction": "fake", "confidence": 0.86},
                {"frame_index": 4, "prediction": "fake", "confidence": 0.91}
            ],
            "demo_mode": True
        })

    content = await _read_upload_with_limit(file, MAX_VIDEO_SIZE_BYTES)
    tmp_path = None
    try:
        from ml.inference import predict_video
        tmp_path = _write_temp_file(content, Path(file.filename).suffix)
        result = predict_video(tmp_path)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Video prediction failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Video prediction failed: {exc}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")

    ext = Path(file.filename).suffix.lower()
    allowed = ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_VIDEO_EXTENSIONS)
    _validate_extension(file.filename, allowed)

    if os.getenv("SMOKE_TEST_MODE", "").lower() == "true":
        LOGGER.info("SMOKE_TEST_MODE active: Returning mock analyze result")
        
        # Determine if we're dealing with an image or video
        is_image = ext in ALLOWED_IMAGE_EXTENSIONS
        content = await file.read()
        
        if is_image:
            # Simple mock response for image
            response_dict = {
                "media_type": "image",
                "prediction": "Fake",
                "final_prediction": "Fake",
                "confidence": 0.89,
                "reliability": "HIGH",
                "reason": "Synthetic visual signature identified in frequency-domain analysis.",
                "ood_flags": [],
                "cnn_prediction": "Fake",
                "cnn_probability": 0.88,
                "fft_prediction": "Fake",
                "fft_probability": 0.90,
                "fusion_prediction": "Fake",
                "fusion_probability": 0.89,
                "fact_check": {
                    "available": False,
                    "note": "Fact-checking is not available for image files."
                },
                "demo_mode": True,
                # PDF report metadata fallbacks
                "video_name": file.filename,
                "final_decision": "FAKE",
                "final_score": 0.89,
                "final_reliability": "HIGH"
            }
            
            # Generate the mock PDF report for image
            try:
                import uuid
                import shutil
                from ml.pdf_generator import generate_pdf_report
                
                # Clean and prepare evidence directory (since it is mounted and serves the files)
                shutil.rmtree(EVIDENCE_DIR, ignore_errors=True)
                EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
                
                report_id = uuid.uuid4().hex
                report_filename = f"report_{report_id}.pdf"
                report_path = EVIDENCE_DIR / report_filename
                generate_pdf_report(response_dict, str(report_path), EVIDENCE_DIR)
                response_dict["report_url"] = f"/evidence/{report_filename}"
                response_dict["legal_report_url"] = f"/evidence/{report_filename}"
            except Exception as pdf_e:
                LOGGER.error("Failed to generate demo image PDF: %s", pdf_e)
                response_dict["report_url"] = ""
                response_dict["legal_report_url"] = ""
                
            return JSONResponse(content=response_dict)
        else:
            # For video, extract actual frames using OpenCV (no ML loaded) to keep it visual
            import cv2
            import numpy as np
            import shutil
            import uuid
            import time
            from datetime import datetime
            
            # Clean and prepare evidence directory
            shutil.rmtree(EVIDENCE_DIR, ignore_errors=True)
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            
            # Save uploaded video to temp file to read frames
            tmp_video_path = _write_temp_file(content, ext)
            
            cap = cv2.VideoCapture(tmp_video_path)
            frame_paths = []
            try:
                # Extract 5 frames from the video to make the visual timeline real
                total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                if total_frames <= 0:
                    total_frames = 100
                step = max(1, total_frames // 5)
                
                for i in range(5):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, min(i * step, total_frames - 1))
                    ret, frame = cap.read()
                    if not ret:
                        # Fallback: create a dummy color block if read fails
                        frame = np.zeros((480, 640, 3), dtype=np.uint8)
                        cv2.putText(frame, f"Demo Frame {i}", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
                        
                    f_name = f"frame_{i:04d}.jpg"
                    f_path = EVIDENCE_DIR / f_name
                    cv2.imwrite(str(f_path), frame)
                    frame_paths.append((f_name, i * step, frame))
            finally:
                cap.release()
                if os.path.exists(tmp_video_path):
                    os.remove(tmp_video_path)
            
            # Build mock frame results and generate mock face crops and heatmaps
            top_suspicious_frames = []
            frame_scores = []
            evidence_list = []
            
            for f_name, f_idx, frame in frame_paths:
                t_sec = f_idx / 5.0
                t_label = f"{(int(t_sec)//60):02d}:{t_sec%60:04.1f}"
                
                # Mock face crop by taking a center region
                h, w = frame.shape[:2]
                ch, cw = int(h * 0.5), int(w * 0.5)
                cy, cx = h // 2, w // 2
                face_img = frame[cy - ch//2 : cy + ch//2, cx - cw//2 : cx + cw//2]
                face_crop_filename = f"face_{f_name}"
                cv2.imwrite(str(EVIDENCE_DIR / face_crop_filename), face_img)
                
                # Mock heatmap using a Gaussian glow in the center of the face crop
                fh, fw = face_img.shape[:2]
                heatmap = np.zeros_like(face_img)
                cv2.circle(heatmap, (fw // 2, fh // 2), min(fw, fh) // 4, (0, 0, 255), -1)
                heatmap = cv2.GaussianBlur(heatmap, (51, 51), 0)
                heatmap_img = cv2.addWeighted(face_img, 0.6, heatmap, 0.4, 0)
                heatmap_filename = f"heatmap_{f_name}"
                cv2.imwrite(str(EVIDENCE_DIR / heatmap_filename), heatmap_img)
                
                face_bbox = {
                    "left_percent": 25.0,
                    "top_percent": 25.0,
                    "width_percent": 50.0,
                    "height_percent": 50.0
                }
                
                fake_score = 0.88 - (f_idx % 3) * 0.02
                
                frame_scores.append({
                    "frame_index": f_idx,
                    "timestamp_sec": t_sec,
                    "fake_score": fake_score
                })
                
                evidence_list.append({
                    "frame": f_name,
                    "score": fake_score
                })
                
                top_suspicious_frames.append({
                    "frame": f_name,
                    "frame_index": f_idx,
                    "timestamp_sec": t_sec,
                    "timestamp_label": t_label,
                    "score": fake_score,
                    "image_url": f"/evidence/{f_name}",
                    "face_crop_url": f"/evidence/{face_crop_filename}",
                    "gradcam_url": f"/evidence/{heatmap_filename}",
                    "evidence_type": "Strong Multi-Model Agreement",
                    "evidence_explanation": "Demo mode check: Anomalous visual consistency detected in facial regions.",
                    "face_bbox": face_bbox
                })
            
            # Generate a mock spectrogram image for audio
            spec_filename = f"audio_spec_{uuid.uuid4().hex[:8]}.png"
            dummy_spec = np.zeros((128, 256, 3), dtype=np.uint8)
            cv2.randn(dummy_spec, (100, 100, 100), (30, 30, 30))
            for x in range(0, 256, 40):
                cv2.line(dummy_spec, (x, 0), (x, 128), (50, 0, 50), 1)
            for y in range(0, 128, 20):
                cv2.line(dummy_spec, (y, 0), (y, 256), (0, 50, 50), 1)
            dummy_spec = cv2.applyColorMap(dummy_spec, cv2.COLORMAP_VIRIDIS)
            cv2.imwrite(str(EVIDENCE_DIR / spec_filename), dummy_spec)
            
            audio_metadata = {
                "available": True,
                "label": "fake",
                "confidence": 0.86,
                "prediction": "fake",
                "probability": 0.86,
                "audio_reliability": 85,
                "reliability_level": "HIGH",
                "explanation": "Acoustic patterns exhibit anomalous frequency gaps typical of generative vocal cloning models.",
                "suspicious_segments": [
                    {"start_sec": 0.5, "end_sec": 1.2, "score": 0.86, "type": "Synthesized Voice"}
                ],
                "evidence_images": [f"/evidence/{spec_filename}"]
            }
            
            # Construct response dict
            response_dict = {
                "analysis_type": "video",
                "media_type": "video",
                "final_decision": "FAKE",
                "final_score": 0.87,
                "final_reliability": "HIGH",
                "smoothing": "moving_average_window_3",
                "metrics": {
                    "weighted_mean": 0.87,
                    "top_k_mean": 0.88,
                    "max_score": 0.88,
                    "variance": 0.002,
                    "mean_diff": 0.01,
                    "frames_processed": 5,
                    "fake_frame_ratio": 1.0,
                    "real_frame_ratio": 0.0
                },
                "frame_scores": frame_scores,
                "top_5_frames": evidence_list,
                "top_suspicious_frames": top_suspicious_frames,
                "video_name": file.filename,
                "video": {
                    "decision": "FAKE",
                    "fake_score": 0.87,
                    "reliability": "HIGH",
                    "metrics": {
                        "weighted_mean": 0.87,
                        "top_k_mean": 0.88,
                        "max_score": 0.88,
                        "variance": 0.002,
                        "mean_diff": 0.01,
                        "frames_processed": 5,
                        "fake_frame_ratio": 1.0,
                        "real_frame_ratio": 0.0
                    },
                    "top_suspicious_frames": top_suspicious_frames
                },
                "audio": audio_metadata,
                "demo_mode": True
            }
            
            # Add fusion, report, metadata, and notice
            from ml.fusion import fuse_modalities
            response_dict["fusion"] = fuse_modalities(response_dict["video"], response_dict["audio"])
            
            # Generate the real PDF report from the mock response dict!
            try:
                from ml.pdf_generator import generate_pdf_report
                report_id = uuid.uuid4().hex
                report_filename = f"report_{report_id}.pdf"
                report_path = EVIDENCE_DIR / report_filename
                generate_pdf_report(response_dict, str(report_path), EVIDENCE_DIR)
                response_dict["report_url"] = f"/evidence/{report_filename}"
                response_dict["legal_report_url"] = f"/evidence/{report_filename}"
            except Exception as pdf_e:
                LOGGER.error("Failed to generate demo PDF: %s", pdf_e)
                response_dict["report_url"] = ""
                response_dict["legal_report_url"] = ""
                
            try:
                # Add legal notice and metadata
                metadata = {
                    "filename": file.filename,
                    "duration_sec": 1.0,
                    "num_frames": 5,
                    "file_size_mb": len(content) / (1024 * 1024),
                    "created_at": datetime.now().isoformat()
                }
                # Ensure we don't overwrite nested structures
                for k, v in metadata.items():
                    if k not in response_dict:
                        response_dict[k] = v
                        
                notice = generate_legal_notice(metadata)
                response_dict["legal_notice"] = notice if notice else ""
                
                # Mock fact-check verdict
                response_dict["fact_check"] = {
                    "available": True,
                    "verdict": "Unverified (Smoke Test Demo)",
                    "source": "Demo Factcheck Database",
                    "url": "http://localhost:8001"
                }
            except Exception as e:
                LOGGER.error("Error generating demo metadata/legal info: %s", e)
                
            return JSONResponse(content=response_dict)

    size_limit = MAX_IMAGE_SIZE_BYTES if ext in ALLOWED_IMAGE_EXTENSIONS else MAX_VIDEO_SIZE_BYTES
    content = await _read_upload_with_limit(file, size_limit)
    tmp_path = None
    try:
        from datetime import datetime
        print(f"[{datetime.now()}] [VIDEO ANALYSIS BEGIN]")
        models = get_img_models()
        from image_inference import infer_image
        tmp_path = _write_temp_file(content, ext)
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            res = infer_image(
                Path(tmp_path),
                cnn_model=models["cnn_model"],
                fft_model=models["fft_model"],
                bundle=models["bundle"],
                device=models["device"],
                cnn_transform=models["cnn_transform"],
                fft_cfg=models["fft_cfg"],
                dataset_mean=models["dataset_mean"],
                dataset_std=models["dataset_std"],
                radial_mask=models["radial_mask"],
                face_crop=True,
                skip_no_face=False
            )
            return JSONResponse(content={
                "media_type": "image",
                # Frontend-expected key names
                "prediction": str(getattr(res, "label_final", "")).capitalize(),
                "final_prediction": str(getattr(res, "label_final", "")).capitalize(),
                "confidence": float(getattr(res, "confidence", 0.0)),
                "reliability": str(getattr(res, "reliability", "")),
                "reason": str(getattr(res, "reason", "")),
                "ood_flags": list(res.ood_flags) if isinstance(getattr(res, "ood_flags", None), (list, tuple)) else [],
                # CNN branch
                "cnn_prediction": str(getattr(res.cnn, "label", "")) if res.cnn else "",
                "cnn_probability": float(getattr(res.cnn, "prob_fake", 0.0)) if res.cnn else 0.0,
                # FFT branch
                "fft_prediction": str(getattr(res.fft, "label", "")) if res.fft else "",
                "fft_probability": float(getattr(res.fft, "prob_fake", 0.0)) if res.fft else 0.0,
                # Fusion branch
                "fusion_prediction": str(getattr(res, "label_final", "")).capitalize(),
                "fusion_probability": float(getattr(res, "prob_final", 0.0)),
                "fact_check": {
                    "available": False,
                    "note": "Fact-checking is not available for image files."
                }
            })
        else:
            import cv2
            import numpy as np
            import shutil
            
            shutil.rmtree(EVIDENCE_DIR, ignore_errors=True)
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            
            def extract_frames(v_path, o_dir, target_fps=5, max_frames=100):
                os.makedirs(o_dir, exist_ok=True)
                cap = cv2.VideoCapture(str(v_path))
                fps = cap.get(cv2.CAP_PROP_FPS)
                if not fps or fps != fps or fps <= 0:
                    fps = 30
                frame_interval = int(round(fps / target_fps))
                if frame_interval < 1:
                    frame_interval = 1
                count = 0
                saved_count = 0
                f_paths = []
                while True:
                    ret = cap.grab()
                    if not ret: break
                    
                    if count % frame_interval == 0:
                        ret, frame = cap.retrieve()
                        if not ret: break
                        f_path = os.path.join(o_dir, f"frame_{saved_count:04d}.jpg")
                        cv2.imwrite(f_path, frame)
                        f_paths.append(f_path)
                        saved_count += 1
                        if saved_count >= max_frames: break
                    count += 1
                cap.release()
                return f_paths


            import time
            from ml.audio_extractor import extract_audio
            t_start = time.time()
            
            t_audio_start = time.time()
            audio_metadata = extract_audio(tmp_path)
            t_audio_extract = time.time() - t_audio_start
            print(f"[{datetime.now()}] [TIMING] Audio Extraction: {t_audio_extract:.2f}s")
            
            from ml.audio_detector import analyze_audio
            if audio_metadata.get("available") and "wav_path" in audio_metadata:
                t_audio_analyze_start = time.time()
                analysis_result = analyze_audio(Path(audio_metadata["wav_path"]))
                audio_metadata.update(analysis_result)
                try:
                    os.remove(audio_metadata["wav_path"])
                except:
                    pass
                del audio_metadata["wav_path"]
                print(f"[{datetime.now()}] [TIMING] Audio Analysis: {time.time() - t_audio_analyze_start:.2f}s")

            
            t_extract_start = time.time()
            temp_dir = Path(tempfile.mkdtemp(dir=str(UPLOAD_DIR)))
            frame_paths = extract_frames(tmp_path, temp_dir, target_fps=5, max_frames=100)
            t_extract = time.time() - t_extract_start
            
            if not frame_paths:
                raise HTTPException(status_code=500, detail="No frames extracted from video")
                
            frame_results = []
            
            t_mtcnn_total = 0.0
            t_cnn_total = 0.0
            t_fft_total = 0.0
            t_sort = 0.0
            t_gradcam_total = 0.0
            t_frame_loop_total = 0.0
            
            for fp in frame_paths:
                try:
                    from image_inference import infer_image
                    res = infer_image(
                        Path(fp),
                        cnn_model=IMG_MODELS["cnn_model"],
                        fft_model=IMG_MODELS["fft_model"],
                        bundle=IMG_MODELS["bundle"],
                        device=IMG_MODELS["device"],
                        cnn_transform=IMG_MODELS["cnn_transform"],
                        fft_cfg=IMG_MODELS["fft_cfg"],
                        dataset_mean=IMG_MODELS["dataset_mean"],
                        dataset_std=IMG_MODELS["dataset_std"],
                        radial_mask=IMG_MODELS["radial_mask"],
                        face_crop=True,
                        skip_no_face=False
                    )
                    t_mtcnn_total += getattr(res, "time_mtcnn", 0.0)
                    t_cnn_total += getattr(res, "time_cnn", 0.0)
                    t_fft_total += getattr(res, "time_fft", 0.0)
                    
                    frame_results.append({
                        "frame": Path(fp).name,
                        "raw_prob_final": res.prob_final,
                        "prob_final": res.prob_final,
                        "label_final": res.label_final,
                        "confidence": res.confidence,
                        "reliability": res.reliability,
                        "cnn_prob": float(getattr(res.cnn, "prob_fake", 0.0)) if getattr(res, "cnn", None) else 0.0,
                        "fft_prob": float(getattr(res.fft, "prob_fake", 0.0)) if getattr(res, "fft", None) else 0.0,
                        "crop_x": getattr(res, "crop_x", None),
                        "crop_y": getattr(res, "crop_y", None),
                        "crop_width": getattr(res, "crop_width", None),
                        "crop_height": getattr(res, "crop_height", None),
                        "original_width": getattr(res, "original_width", None),
                        "original_height": getattr(res, "original_height", None),
                        "face_crop_img": getattr(res, "face_crop_img", None),
                    })
                except Exception as e:
                    LOGGER.error(f"Error on {fp}: {e}")

            if not frame_results:
                raise HTTPException(status_code=500, detail="No successful inferences on video frames")
                
            t_sort_start = time.time()
            raw_probs = [r["raw_prob_final"] for r in frame_results]
            smoothed_probs = []
            for i in range(len(raw_probs)):
                start = max(0, i - 1)
                end = min(len(raw_probs), i + 2)
                window = raw_probs[start:end]
                smoothed_probs.append(sum(window) / len(window))
                
            for r, sp in zip(frame_results, smoothed_probs):
                r["prob_final"] = sp
                r["label_final"] = "FAKE" if sp >= 0.5 else "REAL"
                r["confidence"] = sp if r["label_final"] == "FAKE" else 1.0 - sp
                
            rel_weights = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.4}
            probs = [r["prob_final"] for r in frame_results]
            weights = [r["confidence"] * rel_weights.get(r["reliability"], 0.4) for r in frame_results]
            
            w_sum = sum(weights)
            weighted_mean = sum(p * w for p, w in zip(probs, weights)) / w_sum if w_sum > 0 else 0.5
            
            probs_sorted = sorted(probs, reverse=True)
            k = max(5, int(len(probs) * 0.1))
            k = min(k, len(probs))
            top_k_mean = sum(probs_sorted[:k]) / k if k > 0 else 0.5
            
            max_score = max(probs)
            
            final_score = 0.65 * weighted_mean + 0.25 * top_k_mean + 0.10 * max_score
            
            probs_np = np.array(probs)
            variance = float(np.var(probs_np)) if len(probs) > 1 else 0.0
            diffs = np.abs(probs_np[1:] - probs_np[:-1]) if len(probs) > 1 else np.array([0.0])
            mean_diff = float(np.mean(diffs))
            temporal_diff = mean_diff
            
            fake_frames = sum(1 for r in frame_results if r["label_final"] == "FAKE")
            total_frames = len(frame_results)
            fake_frame_ratio = fake_frames / total_frames if total_frames > 0 else 0.0
            real_frame_ratio = 1.0 - fake_frame_ratio
            
            final_decision = "FAKE" if final_score >= 0.5 else "REAL"
            
            if final_score >= 0.75 and fake_frame_ratio >= 0.70 and temporal_diff < 0.25:
                final_rel = "HIGH"
            elif final_score >= 0.65 and fake_frame_ratio >= 0.60:
                final_rel = "MEDIUM"
            else:
                final_rel = "LOW"
                
            sorted_frames = sorted(frame_results, key=lambda x: x["prob_final"], reverse=True)
            top_5_frames = sorted_frames[:5]
            
            # Discard face_crop_img for non-top-5 frames to save memory
            top_5_names = set(r["frame"] for r in top_5_frames)
            for r in frame_results:
                if r["frame"] not in top_5_names:
                    r["face_crop_img"] = None
                    
            t_sort = time.time() - t_sort_start
            
            evidence_list = []
            top_suspicious_frames = []
            frame_scores = []
            
            # Map filename like "frame_0037.jpg" to its index, defaulting to iteration order
            for i, r in enumerate(frame_results):
                f_name = r["frame"]
                try:
                    f_idx = int(f_name.split("_")[1].split(".")[0])
                except Exception:
                    f_idx = i
                t_sec = f_idx / 5.0
                frame_scores.append({
                    "frame_index": f_idx,
                    "timestamp_sec": t_sec,
                    "fake_score": float(r["prob_final"])
                })
            
            for i, r in enumerate(top_5_frames):
                f_name = r["frame"]
                try:
                    f_idx = int(f_name.split("_")[1].split(".")[0])
                except Exception:
                    f_idx = i
                t_sec = f_idx / 5.0
                t_label = f"{(int(t_sec)//60):02d}:{t_sec%60:04.1f}"
                
                cnn_prob = r.get("cnn_prob", 0.0)
                fft_prob = r.get("fft_prob", 0.0)
                
                # Check neighbors
                neighbors_high = False
                if len(frame_results) > 1:
                    orig_idx = next((idx for idx, fr in enumerate(frame_results) if fr["frame"] == f_name), -1)
                    if orig_idx != -1:
                        has_prev = orig_idx > 0
                        has_next = orig_idx < len(frame_results) - 1
                        prev_high = has_prev and frame_results[orig_idx - 1]["prob_final"] >= 0.7
                        next_high = has_next and frame_results[orig_idx + 1]["prob_final"] >= 0.7
                        
                        if has_prev and has_next:
                            neighbors_high = prev_high and next_high
                        elif has_prev:
                            neighbors_high = prev_high
                        elif has_next:
                            neighbors_high = next_high

                if cnn_prob >= 0.7 and fft_prob >= 0.7:
                    evidence_type = "Strong Multi-Model Agreement"
                    evidence_explanation = "Both the spatial CNN detector and frequency-domain detector independently identified strong signs of manipulation."
                elif cnn_prob >= 0.7 and fft_prob < 0.7:
                    evidence_type = "Visual Face Anomaly"
                    evidence_explanation = "The spatial detector identified unusual facial patterns that differ from authentic video characteristics."
                elif fft_prob >= 0.7 and cnn_prob < 0.7:
                    evidence_type = "Frequency Artifact Detected"
                    evidence_explanation = "The frequency-domain detector identified abnormal spectral patterns commonly associated with synthetic media generation."
                elif neighbors_high:
                    evidence_type = "Temporal Consistency Anomaly"
                    evidence_explanation = "Multiple adjacent frames show similar manipulation signals, suggesting persistent alteration rather than a single-frame anomaly."
                else:
                    evidence_type = "Low Quality Evidence"
                    evidence_explanation = "The model detected suspicious behavior but evidence quality is lower due to limited visual information."
                
                face_bbox = None
                cx = r.get("crop_x")
                cy = r.get("crop_y")
                cw = r.get("crop_width")
                ch = r.get("crop_height")
                ow = r.get("original_width")
                oh = r.get("original_height")
                
                if cx is not None and cy is not None and cw is not None and ch is not None and ow and oh:
                    face_bbox = {
                        "left_percent": (float(cx) / float(ow)) * 100.0,
                        "top_percent": (float(cy) / float(oh)) * 100.0,
                        "width_percent": (float(cw) / float(ow)) * 100.0,
                        "height_percent": (float(ch) / float(oh)) * 100.0
                    }
                
                face_crop_url = None
                gradcam_url = None
                
                # Copy frame to evidence dir
                src_file = temp_dir / f_name
                if src_file.exists():
                    shutil.copy2(src_file, EVIDENCE_DIR / f_name)
                    
                    try:
                        from datetime import datetime
                        print(f"[{datetime.now()}] [GRADCAM BEGIN]")
                        t_gc_start = time.time()
                        from ml.gradcam import GradCAM, overlay_heatmap
                        import cv2
                        
                        face_img = r.get("face_crop_img", None)
                        if face_img is not None:
                            # Save face crop
                            face_crop_path = EVIDENCE_DIR / f"face_{f_name}"
                            cv2.imwrite(str(face_crop_path), cv2.cvtColor(face_img, cv2.COLOR_RGB2BGR))
                            face_crop_url = f"/evidence/face_{f_name}"
                            
                            # Grad-CAM
                            tensor = IMG_MODELS["cnn_transform"](image=face_img)["image"].unsqueeze(0).to(IMG_MODELS["device"], non_blocking=True).float()
                            gradcam = GradCAM(IMG_MODELS["cnn_model"], IMG_MODELS["cnn_model"].features[-1])
                            cam = gradcam.generate(tensor)
                            heatmap_img = overlay_heatmap(face_img, cam, alpha=0.5)
                            
                            heatmap_path = EVIDENCE_DIR / f"heatmap_{f_name}"
                            cv2.imwrite(str(heatmap_path), cv2.cvtColor(heatmap_img, cv2.COLOR_RGB2BGR))
                            gradcam_url = f"/evidence/heatmap_{f_name}"
                            
                        t_gradcam_total += (time.time() - t_gc_start)
                        print(f"[{datetime.now()}] [GRADCAM END]")
                    except Exception as e:
                        print(f"Error generating Grad-CAM for {f_name}: {e}")
                        from datetime import datetime
                        print(f"[{datetime.now()}] [GRADCAM END]")
                    
                evidence_list.append({
                    "frame": f_name,
                    "score": r["prob_final"]
                })
                top_suspicious_frames.append({
                    "frame": f_name,
                    "frame_index": f_idx,
                    "timestamp_sec": t_sec,
                    "timestamp_label": t_label,
                    "score": r["prob_final"],
                    "image_url": f"/evidence/{f_name}",
                    "face_crop_url": face_crop_url,
                    "gradcam_url": gradcam_url,
                    "evidence_type": evidence_type,
                    "evidence_explanation": evidence_explanation,
                    "face_bbox": face_bbox
                })
                
            shutil.rmtree(temp_dir, ignore_errors=True)

            t_total = time.time() - t_start
            print(f"[{datetime.now()}] [TIMING] Frame Extraction: {t_extract:.2f}s")
            print(f"[{datetime.now()}] [TIMING] Face Detection Total: {t_mtcnn_total:.2f}s")
            print(f"[{datetime.now()}] [TIMING] CNN Total: {t_cnn_total:.2f}s")
            print(f"[{datetime.now()}] [TIMING] FFT Total: {t_fft_total:.2f}s")
            print(f"[{datetime.now()}] [TIMING] Sorting/Ranking: {t_sort:.2f}s")
            print(f"[{datetime.now()}] [TIMING] GradCAM Total: {t_gradcam_total:.2f}s")
            print(f"[{datetime.now()}] [TIMING] Total Analysis: {t_total:.2f}s")

            response_dict = {
                # Legacy top-level fields (backward compatibility)
                "analysis_type": "video",
                "media_type": "video",
                "final_decision": final_decision,
                "final_score": final_score,
                "final_reliability": final_rel,
                "smoothing": "moving_average_window_3",
                "metrics": {
                    "weighted_mean": weighted_mean,
                    "top_k_mean": top_k_mean,
                    "max_score": max_score,
                    "variance": variance,
                    "mean_diff": mean_diff,
                    "frames_processed": total_frames,
                    "fake_frame_ratio": fake_frame_ratio,
                    "real_frame_ratio": real_frame_ratio
                },
                "frame_scores": frame_scores,
                "top_5_frames": evidence_list,
                "top_suspicious_frames": top_suspicious_frames,
                "video_name": file.filename,

                # New Modality Schema
                "video": {
                    "decision": final_decision,
                    "fake_score": final_score,
                    "reliability": final_rel,
                    "metrics": {
                        "weighted_mean": weighted_mean,
                        "top_k_mean": top_k_mean,
                        "max_score": max_score,
                        "variance": variance,
                        "mean_diff": mean_diff,
                        "frames_processed": total_frames,
                        "fake_frame_ratio": fake_frame_ratio,
                        "real_frame_ratio": real_frame_ratio
                    },
                    "top_suspicious_frames": top_suspicious_frames
                },
                "audio": audio_metadata
            }
            
            from ml.fusion import fuse_modalities
            response_dict["fusion"] = fuse_modalities(response_dict["video"], response_dict["audio"])
            
            try:
                import uuid
                from ml.pdf_generator import generate_pdf_report
                print(f"[{datetime.now()}] [PDF BEGIN]")
                t_pdf_start = time.time()
                report_id = uuid.uuid4().hex
                report_filename = f"report_{report_id}.pdf"
                report_path = EVIDENCE_DIR / report_filename
                generate_pdf_report(response_dict, str(report_path), EVIDENCE_DIR)
                response_dict["report_url"] = f"/evidence/{report_filename}"
                response_dict["legal_report_url"] = f"/evidence/{report_filename}"
                print(f"[{datetime.now()}] [PDF END] ({(time.time() - t_pdf_start):.2f}s)")
            except Exception as pdf_e:
                print(f"Failed to generate PDF: {pdf_e}")

            try:
                metadata = create_metadata(tmp_path, final_decision, final_score)
                # Ensure we don't overwrite the nested video/audio keys if create_metadata has overlapping old keys
                for k, v in metadata.items():
                    if k not in response_dict:
                        response_dict[k] = v
                
                notice = generate_legal_notice(metadata)
                response_dict["legal_notice"] = notice if notice else ""
                
                try:
                    factcheck_res = run_factcheck_pipeline(tmp_path, media_type="video")
                    response_dict["fact_check"] = factcheck_res
                except Exception as e:
                    LOGGER.exception("Fact-check pipeline failed: %s", e)
                    response_dict["fact_check"] = {"available": False, "warnings": [str(e)]}
            except Exception as e:
                LOGGER.error(f"Error generating metadata/legal info: {e}")

            return JSONResponse(content=response_dict)
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Analyze endpoint failed: %s", exc)
        return JSONResponse(content={"error": f"Processing failed: {exc}"}, status_code=500)
    finally:
        from datetime import datetime
        print(f"[{datetime.now()}] [VIDEO ANALYSIS END]")
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

