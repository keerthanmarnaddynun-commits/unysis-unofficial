"""
Placeholder forensic / ML values for demo and development.
Replace with real pipeline output when available.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from schemas import LegalPacketRequest, TargetRole

IST = timezone(timedelta(hours=5, minutes=30))

# Dummy embeddings aligned with mock Qdrant figures in resolver.py
DUMMY_FACE_EMBEDDING = [0.03] * 512
DUMMY_VOICE_EMBEDDING = [0.04] * 256

DUMMY_DEFAULTS: dict[str, Any] = {
    "system": {
        "analyst_id": "DEMO-ANALYST-001",
        "terminal_mac_address": "00:11:22:33:44:55",
        "workstation_serial_number": "DEMO-WS-2026-0001",
    },
    "file": {
        "filename": "demo_deepfake_sample.mp4",
        "file_size_bytes": 10485760,
        "container_format": "mp4",
        "sha256_hash": "b94d27b9934d3e08a52e52d7da7dae55cfe5f806fb7c93f00039b7c69b6c4220",
    },
    "visual": {
        "spatial_cnn_manipulation_probability": 0.92,
        "face_mesh_landmark_variance": 0.075,
        "lip_sync_alignment_error_ms": 135.0,
    },
    "acoustic": {
        "tts_synthetic_probability": 0.88,
        "spectrogram_pitch_mismatch_ratio": 0.39,
        "anti_spoofing_nn_confidence": 0.11,
    },
    "extended_visual": {
        "illumination_inconsistency_score": 0.71,
        "shadow_geometry_inconsistency_score": 0.66,
        "color_grading_anomaly_score": 0.59,
        "temporal_flicker_score": 0.55,
        "facial_boundary_artifact_score": 0.62,
    },
    "risk": {
        "ncii_indicator": False,
        "sexual_harassment_indicator": False,
        "synthetic_confidence": 0.9,
    },
}


def build_dummy_payload_dict(
    *,
    politician_name: str = "Shri Demo Politician",
    role: TargetRole | str = TargetRole.ACTIVE_CANDIDATE,
    party_affiliation: str | None = "Demo National Party",
    constituency: str | None = "Demo Lok Sabha Constituency",
    analyst_notes: str | None = (
        "Dummy run: lip-sync mismatch observed; face lighting inconsistent; "
        "shadows on jawline appear unnatural."
    ),
) -> dict[str, Any]:
    """Full API payload dict using placeholder forensic values."""
    if isinstance(role, str):
        role = TargetRole(role)

    now = datetime.now(IST)
    data = {
        **DUMMY_DEFAULTS,
        "system": {
            **DUMMY_DEFAULTS["system"],
            "ingestion_timestamp": now.isoformat(),
        },
        "biometrics": {
            "arcface_visual_embedding": list(DUMMY_FACE_EMBEDDING),
            "ecapa_voiceprint_embedding": list(DUMMY_VOICE_EMBEDDING),
        },
        "target": {
            "politician_name": politician_name,
            "party_affiliation": party_affiliation,
            "constituency": constituency,
            "role": role.value,
            "analyst_notes": analyst_notes,
        },
    }
    return data


def build_dummy_request(
    *,
    politician_name: str = "Shri Demo Politician",
    role: TargetRole | str = TargetRole.ACTIVE_CANDIDATE,
    party_affiliation: str | None = "Demo National Party",
    constituency: str | None = "Demo Lok Sabha Constituency",
    analyst_notes: str | None = None,
) -> LegalPacketRequest:
    return LegalPacketRequest.model_validate(
        build_dummy_payload_dict(
            politician_name=politician_name,
            role=role,
            party_affiliation=party_affiliation,
            constituency=constituency,
            analyst_notes=analyst_notes,
        )
    )


def dummy_metrics_json(
    *,
    politician_name: str = "Shri Demo Politician",
    role: TargetRole | str = TargetRole.ACTIVE_CANDIDATE,
) -> str:
    """JSON string for submit form (excludes target — form adds that)."""
    import json

    data = build_dummy_payload_dict(politician_name=politician_name, role=role)
    del data["target"]
    return json.dumps(data, indent=2)
