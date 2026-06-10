import numpy as np

def detect_ood_and_quality(waveform_np, sample_rate=16000):
    """
    Analyzes a 1D numpy array waveform for OOD (Out-of-Distribution) and Quality metrics.
    waveform_np: numpy array of shape (N,) float32 in range [-1.0, 1.0]
    """
    quality_reasons = []
    ood_reasons = []
    
    if len(waveform_np) == 0:
        return {
            "is_unreliable": True,
            "ood_score": 1.0,
            "quality_score": 0.0,
            "ood_reasons": ["empty audio"],
            "quality_reasons": ["no audio data"]
        }
        
    duration = len(waveform_np) / sample_rate
    
    # 1. Clipping detection
    clipping_ratio = np.sum(np.abs(waveform_np) > 0.99) / len(waveform_np)
    if clipping_ratio > 0.05:
        quality_reasons.append(f"high clipping ({clipping_ratio*100:.1f}%)")
    elif clipping_ratio > 0.01:
        quality_reasons.append(f"minor clipping ({clipping_ratio*100:.1f}%)")
        
    # 2. Silence detection
    # Compute RMS energy in 50ms frames
    frame_length = int(0.05 * sample_rate)
    if frame_length == 0:
        frame_length = 1
        
    num_frames = len(waveform_np) // frame_length
    if num_frames == 0:
        rms_energy = np.array([np.sqrt(np.mean(waveform_np**2))])
    else:
        frames = waveform_np[:num_frames * frame_length].reshape(num_frames, frame_length)
        rms_energy = np.sqrt(np.mean(frames**2, axis=1))
        
    silence_threshold = 0.01
    silent_frames = np.sum(rms_energy < silence_threshold)
    silence_ratio = silent_frames / max(len(rms_energy), 1)
    
    if silence_ratio > 0.9:
        ood_reasons.append(f"mostly silence ({silence_ratio*100:.1f}%)")
    elif silence_ratio > 0.5:
        quality_reasons.append(f"high silence ratio ({silence_ratio*100:.1f}%)")
        
    # 3. Simple SNR estimate (ratio of peak energy to median energy)
    peak_energy = np.percentile(rms_energy, 95) if len(rms_energy) > 0 else 0
    noise_floor = np.percentile(rms_energy, 5) if len(rms_energy) > 0 else 0
    
    # Avoid div by zero
    if noise_floor < 1e-6:
        noise_floor = 1e-6
        
    snr_db = 20 * np.log10((peak_energy + 1e-6) / noise_floor)
    
    if snr_db < 10:
        ood_reasons.append(f"extremely noisy (SNR {snr_db:.1f}dB)")
    elif snr_db < 20:
        quality_reasons.append(f"low SNR ({snr_db:.1f}dB)")
        
    # 4. Speech coverage and duration
    speech_coverage = 1.0 - silence_ratio
    if duration < 2.0:
        ood_reasons.append(f"too short ({duration:.1f}s)")
        
    if speech_coverage < 0.2 and duration > 2.0:
        quality_reasons.append("low speech coverage")
        
    # Calculate Quality Score (0.0 to 1.0)
    # Base 1.0
    quality_score = 1.0
    quality_score -= min(0.3, clipping_ratio * 2.0)
    quality_score -= min(0.3, silence_ratio * 0.5)
    
    if snr_db < 20:
        quality_score -= 0.2
    if duration < 3.0:
        quality_score -= 0.1
        
    quality_score = float(np.clip(quality_score, 0.0, 1.0))
    
    # Calculate OOD Score (0.0 to 1.0) - higher means more likely to be out of distribution
    ood_score = 0.0
    if duration < 2.0:
        ood_score += 0.8
    if silence_ratio > 0.9:
        ood_score += 0.8
    if snr_db < 10:
        ood_score += 0.6
        
    ood_score = float(np.clip(ood_score, 0.0, 1.0))
    
    is_unreliable = len(ood_reasons) > 0 or ood_score > 0.7
    
    return {
        "is_unreliable": is_unreliable,
        "ood_score": ood_score,
        "quality_score": quality_score,
        "ood_reasons": ood_reasons,
        "quality_reasons": quality_reasons,
        "snr_db": float(snr_db),
        "silence_ratio": float(silence_ratio),
        "clipping_ratio": float(clipping_ratio)
    }
