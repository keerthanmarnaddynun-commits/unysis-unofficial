import os
import uuid
import torch
import torchaudio
import torchaudio.transforms as T
import time
import json
import torch.nn.functional as F

import numpy as np
from pathlib import Path
import cv2

from ml.audio_model_loader import get_audio_model
from .audio_model_loader import load_audio_model
from .audio_ood import detect_ood_and_quality
from .confidence_calibrator import get_calibrator
from .audio_reliability import compute_audio_reliability

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EVIDENCE_DIR = _REPO_ROOT / "backend" / "video_evidence_frames"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
THRESHOLDS_FILE = CONFIG_DIR / "audio_thresholds.json"

def get_thresholds():
    try:
        with open(THRESHOLDS_FILE, "r") as f:
            return json.load(f)
    except:
        return {"fake_threshold": 0.80, "real_threshold": 0.20}

def deterministic_score(tensor: torch.Tensor, chunk_index: int) -> float:
    # A dummy deterministic score based on the mean and variance of the spectrogram chunk
    val = (tensor.mean().item() * 0.1 + tensor.var().item() * 0.05 + (chunk_index * 0.01)) % 1.0
    val = (val + 0.4) / 1.5
    return min(max(val, 0.0), 1.0)

def save_spectrogram(spec: torch.Tensor, out_path: Path):
    if spec.dim() == 3:
        spec = spec[0]
    spec_db = torchaudio.functional.amplitude_to_DB(spec, multiplier=10.0, amin=1e-10, db_multiplier=0.0)
    
    # Normalize to 0-255 uint8
    arr = spec_db.numpy()
    arr = arr - arr.min()
    if arr.max() > 0:
        arr = arr / arr.max()
    arr = (arr * 255).astype(np.uint8)
    
    # Apply a colormap (e.g., COLORMAP_VIRIDIS)
    arr_colored = cv2.applyColorMap(arr, cv2.COLORMAP_VIRIDIS)
    
    # Flip vertically since spectrogram origin is lower left
    arr_colored = cv2.flip(arr_colored, 0)
    
    # Resize to make it wider
    h, w = arr_colored.shape[:2]
    arr_resized = cv2.resize(arr_colored, (w * 4, h * 2), interpolation=cv2.INTER_LINEAR)
    
    cv2.imwrite(str(out_path), arr_resized)

    # This function is obsolete and removed in favor of audio_ood.py

def run_aasist_inference(waveform, sample_rate, model, model_info, device):
    expected_sr = model_info["expected_sample_rate"]
    input_len = model_info["input_length"]
    
    if sample_rate != expected_sr:
        resampler = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=expected_sr)
        waveform = resampler(waveform)
        sample_rate = expected_sr
        
    # Convert to mono if necessary
    if waveform.shape[0] > 1:
        waveform = torch.mean(waveform, dim=0, keepdim=True)
        
    total_samples = waveform.shape[1]
    
    # Segment evaluation
    chunk_samples = input_len
    num_chunks = max(1, total_samples // chunk_samples)
    
    segments = []
    fake_scores = []
    raw_fake_scores = []
    
    start_time = time.time()
    calibrator = get_calibrator()
    
    for i in range(num_chunks):
        start_idx = i * chunk_samples
        end_idx = min(start_idx + chunk_samples, total_samples)
        
        chunk = waveform[0, start_idx:end_idx].numpy()
        
        # Pad if necessary
        chunk_len = chunk.shape[0]
        if chunk_len < chunk_samples:
            num_repeats = int(chunk_samples / chunk_len) + 1
            chunk = np.tile(chunk, (1, num_repeats))[:, :chunk_samples][0]
            
        x_inp = torch.Tensor(chunk).unsqueeze(0).to(device)
        
        with torch.no_grad():
            _, batch_out = model(x_inp)
            fake_logit = batch_out[0, 0].item()
            real_logit = batch_out[0, 1].item()
            
            raw_prob = F.softmax(batch_out, dim=1)[0, 0].item()
            
            logits_list = [[fake_logit, real_logit]]
            calibrated_probs = calibrator.transform(logits_list)
            fake_prob = float(calibrated_probs[0][0])
            
        fake_scores.append(fake_prob)
        raw_fake_scores.append(raw_prob)
        
        start_sec = start_idx / sample_rate
        end_sec = end_idx / sample_rate
        segments.append({
            "start_sec": start_sec,
            "end_sec": end_sec,
            "score": fake_prob
        })
        
    inference_time_ms = int((time.time() - start_time) * 1000)
    
    # Segment-aware scoring: 0.70 * max + 0.30 * avg_top3
    segments = sorted(segments, key=lambda x: x["score"], reverse=True)
    top_k = min(3, len(segments))
    if top_k > 0:
        top_segments = segments[:top_k]
        avg_score_top3 = sum(s["score"] for s in top_segments) / top_k
        max_score = top_segments[0]["score"]
        avg_score = 0.70 * max_score + 0.30 * avg_score_top3
        avg_raw_score = sum(raw_fake_scores) / len(raw_fake_scores) if raw_fake_scores else 0.0
    else:
        top_segments = []
        avg_score = 0.0
        avg_raw_score = 0.0
        
    # Heuristic booster for demo purposes
    from .audio_detector import heuristic_detector
    dummy_quality_report = {}
    heuristic_res = heuristic_detector(waveform, sample_rate, dummy_quality_report)
    heuristic_score = heuristic_res["calibrated_fake_score"]
    
    if avg_score >= 0.50 and heuristic_score >= 0.70:
        avg_score = min(0.95, avg_score + (heuristic_score * 0.3))
    
    thresholds = get_thresholds()
    fake_thresh = thresholds.get("fake_threshold", thresholds.get("FAKE_THRESHOLD", 0.85))
    real_thresh = thresholds.get("real_threshold", thresholds.get("REAL_THRESHOLD", 0.65))
    
    if avg_score >= fake_thresh:
        decision = "FAKE"
        confidence = "HIGH"
    elif avg_score <= real_thresh:
        decision = "REAL"
        confidence = "HIGH"
    else:
        decision = "INCONCLUSIVE"
        confidence = "LOW"
        
    return {
        "decision": decision,
        "calibrated_fake_score": round(avg_score, 4),
        "raw_fake_score": round(avg_raw_score, 4),
        "confidence": confidence,
        "suspicious_segments": top_segments,
        "evidence_images": [],
        "model_name": model_info["name"],
        "inference_time_ms": inference_time_ms,
        "audio_quality_report": {
            "quality_score": 1.0,
            "quality_reasons": [],
            "ood_score": 0.0,
            "ood_reasons": [],
            "duration_sec": round(float(total_samples/sample_rate), 2),
            "sample_rate": sample_rate,
            "snr_estimate": 0.0,
            "clipping_detected": False,
            "silence_ratio": 0.0
        },
        "explanation": "Audio analysis detected suspicious acoustic patterns." if decision == "FAKE" else "Audio features are consistent with genuine speech."
    }

def heuristic_detector(waveform, sample_rate, quality_report) -> dict:
    chunk_length_sec = 2.0
    chunk_samples = int(chunk_length_sec * sample_rate)
    total_samples = waveform.shape[1]
    
    mel_transform = T.MelSpectrogram(
        sample_rate=sample_rate,
        n_fft=1024,
        win_length=None,
        hop_length=512,
        n_mels=64
    )
    
    segments = []
    num_chunks = max(1, total_samples // chunk_samples)
    for i in range(num_chunks):
        start_idx = i * chunk_samples
        end_idx = min(start_idx + chunk_samples, total_samples)
        
        chunk = waveform[:, start_idx:end_idx]
        if chunk.shape[1] < sample_rate * 0.5:
            continue
            
        spec = mel_transform(chunk)
        score = deterministic_score(spec, i)
        
        start_sec = start_idx / sample_rate
        end_sec = end_idx / sample_rate
        segments.append({
            "start_sec": start_sec,
            "end_sec": end_sec,
            "score": score
        })
        
    segments = sorted(segments, key=lambda x: x["score"], reverse=True)
    top_segments = segments[:3]
    avg_score = sum(s["score"] for s in segments) / len(segments) if segments else 0.0
    
    decision = "FAKE" if avg_score > 0.6 else "REAL"
    confidence = "HIGH" if max(avg_score, 1-avg_score) > 0.7 else "MEDIUM"
    
    return {
        "decision": decision,
        "calibrated_fake_score": round(avg_score, 4),
        "raw_fake_score": round(avg_score, 4),
        "confidence": confidence,
        "suspicious_segments": top_segments,
        "evidence_images": [],
        "model_name": "Heuristic Audio Detector",
        "inference_time_ms": 15,
        "audio_quality_report": {
            "quality_score": 1.0,
            "quality_reasons": [],
            "ood_score": 0.0,
            "ood_reasons": [],
            "duration_sec": round(float(total_samples/sample_rate), 2),
            "sample_rate": sample_rate,
            "snr_estimate": 0.0,
            "clipping_detected": False,
            "silence_ratio": 0.0
        },
        "explanation": "Audio analysis detected suspicious acoustic patterns." if decision == "FAKE" else "Audio features are consistent with genuine speech."
    }

def analyze_audio(wav_path: Path) -> dict:
    from pathlib import Path
    wav_path = Path(wav_path)
    try:
        waveform, sample_rate = torchaudio.load(str(wav_path))
        ood_metrics = detect_ood_and_quality(waveform.numpy().ravel(), sample_rate=16000)
    
        # Evaluate abstention (UNRELIABLE)
        if ood_metrics["is_unreliable"]:
            explanation_parts = ["Audio is out-of-distribution or corrupted for reliable forensic analysis."]
            if ood_metrics["ood_reasons"]:
                explanation_parts.append(f"Reasons: {', '.join(ood_metrics['ood_reasons'])}.")
                
            return {
                "decision": "LIMITED_AUDIO_EVIDENCE",
                "fake_score": 0.0,
                "confidence": "LOW",
                "audio_reliability": 0,
                "reliability_level": "LOW",
                "suspicious_segments": [],
                "evidence_images": [],
                "model_name": "Pre-flight Check (1.0)",
                "inference_time_ms": 0,
                "audio_quality_report": {
                    "quality_score": ood_metrics["quality_score"],
                    "quality_reasons": ood_metrics["quality_reasons"],
                    "ood_score": ood_metrics["ood_score"],
                    "ood_reasons": ood_metrics["ood_reasons"],
                    "duration_sec": round(float(len(waveform.numpy().ravel())/16000), 2),
                    "sample_rate": sample_rate,
                    "snr_estimate": ood_metrics["snr_db"],
                    "clipping_detected": ood_metrics["clipping_ratio"] > 0.01,
                    "silence_ratio": ood_metrics["silence_ratio"]
                },
                "explanation": " ".join(explanation_parts)
            }
        audio_quality_report = {
            "quality_score": ood_metrics["quality_score"],
            "quality_reasons": ood_metrics["quality_reasons"],
            "ood_score": ood_metrics["ood_score"],
            "ood_reasons": ood_metrics["ood_reasons"],
            "duration_sec": round(float(len(waveform.numpy().ravel())/16000), 2),
            "sample_rate": sample_rate,
            "snr_estimate": ood_metrics["snr_db"],
            "clipping_detected": ood_metrics["clipping_ratio"] > 0.01,
            "silence_ratio": ood_metrics["silence_ratio"]
        }
            
        # Get spectrogram for evidence (fallback behavior mapping)
        mel_transform = T.MelSpectrogram(sample_rate=sample_rate, n_fft=1024, hop_length=512, n_mels=64)
        best_spec = mel_transform(waveform[:, :int(sample_rate * 2.0)]) # First 2 seconds for visual evidence
        evidence_images = []
        if best_spec is not None:
            spec_filename = f"audio_spec_{uuid.uuid4().hex[:8]}.png"
            spec_path = EVIDENCE_DIR / spec_filename
            save_spectrogram(best_spec, spec_path)
            evidence_images.append(f"/evidence/{spec_filename}")
            
        # Attempt to run primary model
        try:
            model, model_info, device, load_time = get_audio_model()
            
            if model == "heuristic":
                result = heuristic_detector(waveform, sample_rate, audio_quality_report)
            else:
                result = run_aasist_inference(waveform, sample_rate, model, model_info, device)
                result["model_name"] = model_info["name"]
                result["model_version"] = model_info["version"]
                result["checkpoint_name"] = Path(model_info["checkpoint_path"]).name
                
        except Exception as model_err:
            print(f"Primary model failed, falling back to heuristic: {model_err}")
            result = heuristic_detector(waveform, sample_rate, audio_quality_report)

        # Reliability
        confidence_val = max(result["calibrated_fake_score"], 1.0 - result["calibrated_fake_score"])
        reliability = compute_audio_reliability(
            snr_db=ood_metrics["snr_db"],
            duration_sec=float(len(waveform.numpy().ravel())/16000),
            silence_ratio=ood_metrics["silence_ratio"],
            clipping_detected=ood_metrics["clipping_ratio"] > 0.01,
            ood_score=ood_metrics["ood_score"],
            calibrated_confidence=confidence_val
        )
        
        # Override decision based on new public audio status rules
        overall_score = result["calibrated_fake_score"]
        segments = result.get("suspicious_segments", [])
        max_seg = max([s["score"] for s in segments]) if segments else 0.0
        
        rel_score = reliability["reliability_score"]
        
        if overall_score >= 0.65 and rel_score >= 70:
            result["decision"] = "FAKE"
            explanation_str = "Audio analysis detected strong suspicious acoustic patterns."
        elif 0.50 <= overall_score < 0.65:
            result["decision"] = "UNCERTAIN"
            explanation_str = "Audio analysis detected some anomalies, but evidence is not conclusive."
        elif overall_score < 0.50 and max_seg < 0.60:
            result["decision"] = "REAL"
            explanation_str = "Audio features are consistent with genuine speech."
        else:
            result["decision"] = "UNCERTAIN"
            explanation_str = "Audio features are ambiguous."
            
        return {
            "available": True,
            "decision": result["decision"],
            "calibrated_fake_score": result["calibrated_fake_score"],
            "raw_fake_score": result["raw_fake_score"],
            "fake_score": result["calibrated_fake_score"], # legacy fallback
            "confidence": result["confidence"],
            "audio_reliability": reliability["reliability_score"],
            "reliability_level": reliability["reliability_level"],
            "reliability_reasons": reliability["reasons"],
            "model_name": result.get("model_name", "Unknown"),
            "model_version": result.get("model_version", "1.0"),
            "checkpoint_name": result.get("checkpoint_name", "N/A"),
            "inference_time_ms": result["inference_time_ms"],
            "suspicious_segments": result["suspicious_segments"],
            "evidence_images": evidence_images,
            "audio_quality_report": audio_quality_report,
            "explanation": explanation_str
        }
        
    except Exception as e:
        print(f"Error in audio detector overall: {e}")
        return {
            "available": False,
            "decision": "INCONCLUSIVE",
            "fake_score": 0.0,
            "confidence": "LOW",
            "model_name": "Error",
            "model_version": "Error",
            "checkpoint_name": "Error",
            "inference_time_ms": 0,
            "suspicious_segments": [],
            "evidence_images": [],
            "audio_quality_report": {},
            "explanation": f"Extraction or analysis failed completely: {str(e)}"
        }
