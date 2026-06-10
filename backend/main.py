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
EVIDENCE_DIR = Path("D:/forsen/video_evidence_frames")
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
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR = Path("D:/forsen/video_evidence_frames")
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
            # Create JWT token
            access_token = create_access_token(data={
                "role": doc.get("role"),
                "identifier": doc.get("official_id"),
                "name": doc.get("name"),
                "organization": doc.get("organization")
            })
            
            return {
                "valid": True,
                "access_token": access_token,
                "token_type": "bearer",
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


@app.post("/predict/video")
async def predict_video_endpoint(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    _validate_extension(file.filename, ALLOWED_VIDEO_EXTENSIONS)

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

