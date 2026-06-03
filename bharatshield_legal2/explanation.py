"""Rule-based and ML-extended deepfake explanation builder."""

from __future__ import annotations

from config import settings
from schemas import (
    AcousticForensics,
    DeepfakeExplanation,
    ExplanationFinding,
    ExplanationSeverity,
    ExtendedVisualForensics,
    UserTargetInput,
    VisualForensics,
)


def _add(
    findings: list[ExplanationFinding],
    sources: set[str],
    *,
    category: str,
    severity: ExplanationSeverity,
    plain_language: str,
    metric_ref: str | None = None,
    value: str | None = None,
    source: str = "rule_engine",
) -> None:
    findings.append(
        ExplanationFinding(
            category=category,
            severity=severity,
            plain_language=plain_language,
            metric_ref=metric_ref,
            value=value,
            source=source,
        )
    )
    sources.add(source)


def build_explanation(
    visual: VisualForensics,
    acoustic: AcousticForensics,
    extended: ExtendedVisualForensics | None = None,
    user: UserTargetInput | None = None,
) -> DeepfakeExplanation:
    findings: list[ExplanationFinding] = []
    sources: set[str] = set()

    # Lip-sync / audio-video sync
    if visual.lip_sync_alignment_error_ms > settings.lip_sync_warn_ms:
        sev = (
            ExplanationSeverity.CRITICAL
            if visual.lip_sync_alignment_error_ms > settings.lip_sync_warn_ms * 1.5
            else ExplanationSeverity.HIGH
        )
        _add(
            findings,
            sources,
            category="Audio-Video Sync",
            severity=sev,
            plain_language=(
                "Audio–video lip movement is misaligned, consistent with synthetic dubbing "
                "or post-hoc voice replacement rather than naturally captured speech."
            ),
            metric_ref="lip_sync_alignment_error_ms",
            value=f"{visual.lip_sync_alignment_error_ms:.1f} ms",
        )

    if visual.spatial_cnn_manipulation_probability >= settings.spatial_cnn_warn:
        _add(
            findings,
            sources,
            category="Facial Manipulation",
            severity=ExplanationSeverity.HIGH,
            plain_language=(
                "Spatial facial inconsistencies detected across frames suggest "
                "GAN or deepfake-based facial manipulation."
            ),
            metric_ref="spatial_cnn_manipulation_probability",
            value=f"{visual.spatial_cnn_manipulation_probability:.2%}",
        )

    if visual.face_mesh_landmark_variance >= settings.face_mesh_variance_warn:
        _add(
            findings,
            sources,
            category="3D Face Geometry",
            severity=ExplanationSeverity.MEDIUM,
            plain_language=(
                "3D face mesh landmarks are unstable across the temporal sequence, "
                "indicating inconsistent facial geometry typical of synthetic faces."
            ),
            metric_ref="face_mesh_landmark_variance",
            value=f"{visual.face_mesh_landmark_variance:.4f}",
        )

    if acoustic.tts_synthetic_probability >= settings.tts_synthetic_warn:
        _add(
            findings,
            sources,
            category="Synthetic Voice",
            severity=ExplanationSeverity.HIGH,
            plain_language=(
                "The voice track exhibits characteristics consistent with "
                "text-to-speech or neural voice cloning rather than a live recording."
            ),
            metric_ref="tts_synthetic_probability",
            value=f"{acoustic.tts_synthetic_probability:.2%}",
        )

    if acoustic.spectrogram_pitch_mismatch_ratio >= settings.pitch_mismatch_warn:
        _add(
            findings,
            sources,
            category="Voice Authenticity",
            severity=ExplanationSeverity.MEDIUM,
            plain_language=(
                "Pitch contour and spectrogram features do not match natural speech patterns "
                "for the apparent speaker, suggesting audio synthesis or splicing."
            ),
            metric_ref="spectrogram_pitch_mismatch_ratio",
            value=f"{acoustic.spectrogram_pitch_mismatch_ratio:.2%}",
        )

    if acoustic.anti_spoofing_nn_confidence <= settings.anti_spoofing_low_warn:
        _add(
            findings,
            sources,
            category="Anti-Spoofing",
            severity=ExplanationSeverity.HIGH,
            plain_language=(
                "Anti-spoofing neural network assigns low confidence to bona fide speech, "
                "indicating the audio is likely non-genuine or heavily processed."
            ),
            metric_ref="anti_spoofing_nn_confidence",
            value=f"{acoustic.anti_spoofing_nn_confidence:.2%}",
        )

    # Extended ML metrics (future pipeline)
    if extended:
        ext_checks = [
            (
                extended.illumination_inconsistency_score,
                "Lighting Consistency",
                "illumination_inconsistency_score",
                "Lighting on the face and background shifts unnaturally between frames, "
                "suggesting compositing or generative synthesis rather than a single capture.",
            ),
            (
                extended.shadow_geometry_inconsistency_score,
                "Shadow Geometry",
                "shadow_geometry_inconsistency_score",
                "Shadow direction and softness are inconsistent with the scene light source, "
                "a common artifact in deepfake and face-swap videos.",
            ),
            (
                extended.color_grading_anomaly_score,
                "Color Grading",
                "color_grading_anomaly_score",
                "Skin tone and color grading do not remain consistent across frames; "
                "color boundaries and shadows appear imperfect relative to natural video.",
            ),
            (
                extended.temporal_flicker_score,
                "Temporal Stability",
                "temporal_flicker_score",
                "High-frequency flicker and temporal instability detected at facial boundaries, "
                "consistent with frame-wise generative manipulation.",
            ),
            (
                extended.facial_boundary_artifact_score,
                "Facial Boundaries",
                "facial_boundary_artifact_score",
                "Visible artifacts at the jawline, hairline, or face perimeter suggest "
                "blending of a synthetic face onto an original body.",
            ),
        ]
        for score, category, metric_ref, narrative in ext_checks:
            if score is not None and score >= settings.extended_visual_warn:
                _add(
                    findings,
                    sources,
                    category=category,
                    severity=ExplanationSeverity.HIGH if score >= 0.75 else ExplanationSeverity.MEDIUM,
                    plain_language=narrative,
                    metric_ref=metric_ref,
                    value=f"{score:.2%}",
                    source="ml_metric",
                )

    if user and user.analyst_notes:
        _add(
            findings,
            sources,
            category="Analyst Observation",
            severity=ExplanationSeverity.MEDIUM,
            plain_language=user.analyst_notes.strip(),
            source="analyst_note",
        )

    if not findings:
        summary = (
            "Automated forensic metrics did not exceed configured thresholds; "
            "manual expert review is recommended."
        )
    else:
        critical = sum(1 for f in findings if f.severity in (ExplanationSeverity.CRITICAL, ExplanationSeverity.HIGH))
        summary = (
            f"Media classified as likely synthetically manipulated based on {len(findings)} "
            f"forensic indicator(s), including {critical} high-severity finding(s)."
        )

    return DeepfakeExplanation(
        summary=summary,
        findings=findings,
        sources=sorted(sources),
    )
