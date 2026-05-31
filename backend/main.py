import logging
import os
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from image_inference import (
    resolve_device, load_cnn_model, load_fft_checkpoint, load_fusion_bundle,
    get_transform, load_fft_run_config, load_stats, build_radial_emphasis_mask, infer_image,
    DEFAULT_CNN_MODEL, DEFAULT_FFT_MODEL, DEFAULT_FUSION_BUNDLE, DEFAULT_FFT_RUN_CONFIG, DEFAULT_FFT_STATS
)

from ml.config import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_VIDEO_EXTENSIONS,
    MAX_IMAGE_SIZE_MB,
    MAX_VIDEO_SIZE_MB,
    UPLOAD_DIR,
    setup_logging,
)
from ml.inference import predict_video
from ml.model_loader import get_model
from utils.legal import generate_legal_notice
from utils.metadata import create_metadata


setup_logging()
LOGGER = logging.getLogger(__name__)

app = FastAPI(title="BharatShield Backend", version="1.0.0")
# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

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
def startup_event() -> None:
    import torch
    device = resolve_device(None)
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


@app.post("/predict/video")
async def predict_video_endpoint(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Empty filename")
    _validate_extension(file.filename, ALLOWED_VIDEO_EXTENSIONS)

    content = await _read_upload_with_limit(file, MAX_VIDEO_SIZE_BYTES)
    tmp_path = None
    try:
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
        tmp_path = _write_temp_file(content, ext)
        if ext in ALLOWED_IMAGE_EXTENSIONS:
            res = infer_image(
                Path(tmp_path),
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
            })
        else:
            pred = predict_video(tmp_path)
            result = pred["final_prediction"].capitalize()
            confidence = pred["confidence"]

            metadata = create_metadata(tmp_path, result, confidence)
            notice = generate_legal_notice(metadata)
            metadata["legal_notice"] = notice if notice else ""
            return JSONResponse(content=metadata)
    except HTTPException:
        raise
    except Exception as exc:
        LOGGER.exception("Analyze endpoint failed: %s", exc)
        return JSONResponse(content={"error": f"Processing failed: {exc}"}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

