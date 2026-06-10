def assess_video_quality(video_data: dict) -> str:
    """
    Inputs:
    - frames analyzed (metrics.frames_processed)
    - face detection success ratio (face_bbox/etc, or just frames_processed)
    - evidence availability
    """
    if not video_data or video_data.get('decision') == 'NOT_ANALYZED':
        return 'UNAVAILABLE'
    
    metrics = video_data.get('metrics', {})
    frames_processed = metrics.get('frames_processed', 0)
    
    if frames_processed < 5:
        return 'DEGRADED'
        
    return 'GOOD'

def assess_audio_quality(audio_data: dict) -> str:
    """
    Inputs:
    - audio available
    - duration
    - extraction status
    - reliability
    """
    if not audio_data or not audio_data.get('available', False) or audio_data.get('decision') in ['UNRELIABLE', 'LIMITED_AUDIO_EVIDENCE']:
        return 'UNAVAILABLE'
        
    rel = audio_data.get('audio_reliability', 100)
    if rel < 30:
        return 'UNAVAILABLE'
    elif rel < 50:
        return 'DEGRADED'
        
    duration = audio_data.get('duration_sec', 0.0)
    if duration < 2.0:
        return 'DEGRADED'
        
    return 'GOOD'

def get_confidence_level(score: float) -> str:
    cert = max(score, 1.0 - score)
    if cert > 0.90:
        return 'HIGH'
    elif cert >= 0.70:
        return 'MEDIUM'
    else:
        return 'LOW'

def fuse_modalities(video_data: dict, audio_data: dict) -> dict:
    video_q = assess_video_quality(video_data)
    audio_q = assess_audio_quality(audio_data)
    
    # Weight logic
    q_weights = {'GOOD': 1.0, 'DEGRADED': 0.5, 'UNAVAILABLE': 0.0}
    vw = q_weights[video_q]
    aw = q_weights[audio_q]
    
    # Normalize
    total_w = vw + aw
    if total_w > 0:
        v_contrib = vw / total_w
        a_contrib = aw / total_w
    else:
        v_contrib = 0.0
        a_contrib = 0.0
        
    v_dec = video_data.get('decision', 'NOT_ANALYZED') if video_q != 'UNAVAILABLE' else 'NOT_ANALYZED'
    a_dec = audio_data.get('decision', 'NOT_ANALYZED') if audio_q != 'UNAVAILABLE' else 'NOT_ANALYZED'
    
    v_score = video_data.get('fake_score', 0.0) if video_q != 'UNAVAILABLE' else 0.5
    a_score = audio_data.get('fake_score', 0.0) if audio_q != 'UNAVAILABLE' else 0.5
    
    final_decision = "INCONCLUSIVE"
    source = "UNKNOWN"
    conflict = "NONE"
    explanation = "Analysis indicates inconclusive results."
    final_score = (v_score * v_contrib) + (a_score * a_contrib) if total_w > 0 else 0.5

    # Case 1: Video REAL, Audio REAL
    if v_dec == 'REAL' and a_dec in ['REAL', 'NO_STRONG_ACOUSTIC_ANOMALY']:
        final_decision = 'REAL'
        source = 'VIDEO + AUDIO'
        explanation = "Evidence indicates authentic visual and audio characteristics with no detected anomalies."
    
    # Case 2: Video FAKE, Audio FAKE (Suspicious or High Suspicion)
    elif v_dec == 'FAKE' and a_dec in ['FAKE', 'HIGH_AUDIO_SUSPICION', 'SUSPICIOUS_ACOUSTIC_PATTERNS']:
        final_decision = 'FAKE'
        source = 'VIDEO_PRIMARY_WITH_AUDIO_SUPPORT'
        conflict = 'LOW'
        explanation = "Analysis suggests manipulation across visual stream with supporting acoustic anomalies."
        
    # Case 3: Video FAKE, Audio REAL
    elif v_dec == 'FAKE' and a_dec in ['REAL', 'UNCERTAIN', 'NO_STRONG_ACOUSTIC_ANOMALY', 'LIMITED_AUDIO_EVIDENCE']:
        final_decision = 'FAKE'
        source = 'VIDEO_PRIMARY'
        conflict = 'LOW'
        explanation = "Visual evidence suggests manipulation. Audio did not provide strong contradictory evidence."
        
    # Case 4: Video REAL, Audio FAKE
    elif v_dec == 'REAL' and a_dec in ['FAKE', 'HIGH_AUDIO_SUSPICION']:
        audio_conf = audio_data.get('confidence', 'LOW')
        audio_rel = audio_data.get('audio_reliability', 100)
        if audio_conf == 'HIGH' and audio_q == 'GOOD' and audio_rel > 70:
            final_decision = 'FAKE'
            source = 'AUDIO_DOMINANT'
            conflict = 'LOW'
            explanation = "Audio anomalies indicate likely synthetic or manipulated speech."
        else:
            final_decision = 'INCONCLUSIVE'
            source = 'CONFLICT'
            conflict = 'HIGH'
            explanation = f"Audio suggests manipulation but reliability is insufficient ({audio_rel}/100) to override authentic visual evidence."
            
    # Case 4.5: Video REAL, Audio UNCERTAIN
    elif v_dec == 'REAL' and a_dec in ['UNCERTAIN', 'SUSPICIOUS_ACOUSTIC_PATTERNS', 'LIMITED_AUDIO_EVIDENCE']:
        final_decision = 'REAL'
        source = 'VIDEO_PRIMARY'
        conflict = 'LOW'
        explanation = "Visual evidence indicates authenticity. Audio anomalies were detected but lack sufficient confidence to declare as manipulated."
        
    # Case 5: Video Only
    elif v_dec != 'NOT_ANALYZED' and a_dec == 'NOT_ANALYZED':
        final_decision = v_dec
        source = 'VIDEO_ONLY'
        explanation = f"Analysis suggests the media is {v_dec} based on visual indicators alone."
        
    # Case 6: Audio Only
    elif v_dec == 'NOT_ANALYZED' and a_dec != 'NOT_ANALYZED':
        final_decision = a_dec
        source = 'AUDIO_ONLY'
        explanation = f"Analysis suggests the media is {a_dec} based on audio indicators alone."

    return {
        "final_score": float(final_score),
        "final_decision": final_decision,
        "confidence": get_confidence_level(final_score),
        "decision_source": source,
        "video_quality": video_q,
        "audio_quality": audio_q,
        "modality_contributions": {
            "video": float(v_contrib),
            "audio": float(a_contrib)
        },
        "conflict_level": conflict,
        "explanation": explanation
    }
