def compute_audio_reliability(snr_db, duration_sec, silence_ratio, clipping_detected, ood_score, calibrated_confidence):
    """
    Computes a reliability score for the audio sample (0-100).
    """
    score = 100.0
    reasons = []

    # Penalty for low SNR
    if snr_db < 10:
        penalty = min(50, (10 - snr_db) * 5)
        score -= penalty
        reasons.append(f"Low SNR (-{penalty:.1f})")

    # Penalty for short duration
    if duration_sec < 3.0:
        penalty = min(40, (3.0 - duration_sec) * 15)
        score -= penalty
        reasons.append(f"Short duration (-{penalty:.1f})")

    # Penalty for high silence
    if silence_ratio > 0.5:
        penalty = (silence_ratio - 0.5) * 100
        score -= penalty
        reasons.append(f"High silence (-{penalty:.1f})")

    # Penalty for clipping
    if clipping_detected:
        score -= 20
        reasons.append("Clipping detected (-20.0)")

    # Penalty for high OOD
    if ood_score > 0.5:
        penalty = (ood_score - 0.5) * 100
        score -= penalty
        reasons.append(f"High OOD score (-{penalty:.1f})")
        
    # Penalty for low confidence (model uncertainty)
    if calibrated_confidence < 0.7:
        penalty = (0.7 - calibrated_confidence) * 100
        score -= penalty
        reasons.append(f"Low model confidence (-{penalty:.1f})")

    score = max(0.0, min(100.0, score))
    
    if score >= 80:
        level = "HIGH"
    elif score >= 50:
        level = "MEDIUM"
    else:
        level = "LOW"
        
    if not reasons:
        reasons.append("Audio characteristics are optimal.")
        
    return {
        "reliability_score": int(score),
        "reliability_level": level,
        "reasons": reasons
    }
