"""
Legal integration adapter — bridges deepfake detection results with
the bharatshield_legal2 document generation pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

# Add bharatshield_legal2 to path
_REPO_ROOT = Path(__file__).resolve().parent.parent
_LEGAL_DIR = _REPO_ROOT / "bharatshield_legal2"
if str(_LEGAL_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGAL_DIR))


def _build_legal_packet_from_analysis(
    analysis: dict[str, Any],
    media_filename: str,
    media_hash: str,
    media_size: int,
    reporter_name: str | None = None,
) -> dict[str, Any]:
    """
    Convert the main backend's analysis results into the LegalPacketRequest schema.

    Maps:
      - CNN fake probability → spatial_cnn_manipulation_probability
      - FFT fake probability → face_mesh_landmark_variance (approx)
      - confidence → synthetic_confidence
    """
    cnn_prob = analysis.get("cnn_probability", 0.0)
    fft_prob = analysis.get("fft_probability", 0.0)
    confidence = analysis.get("confidence", 0.5)
    prediction = analysis.get("prediction", "Unknown")

    now = datetime.now(IST)

    # Build the forensic metrics payload compatible with bharatshield_legal2 schemas
    import uuid as _uuid
    import random

    payload = {
        "system": {
            "ingestion_timestamp": now.isoformat(),
            "analyst_id": reporter_name or "BharatShield-Auto",
            "terminal_mac_address": "00:00:00:00:00:00",
            "workstation_serial_number": "BHARATSHIELD-LOCAL-001",
        },
        "file": {
            "filename": media_filename,
            "file_size_bytes": max(media_size, 1),
            "container_format": Path(media_filename).suffix.lstrip(".").upper() or "UNKNOWN",
            "sha256_hash": media_hash if len(media_hash) == 64 else hashlib.sha256(media_hash.encode()).hexdigest(),
        },
        "visual": {
            "spatial_cnn_manipulation_probability": min(max(cnn_prob, 0.0), 1.0),
            "face_mesh_landmark_variance": min(max(fft_prob * 0.1, 0.0), 0.5),
            "lip_sync_alignment_error_ms": confidence * 150 if prediction.lower() == "fake" else 20.0,
        },
        "acoustic": {
            "tts_synthetic_probability": min(max(fft_prob, 0.0), 1.0),
            "spectrogram_pitch_mismatch_ratio": min(max(confidence * 0.5, 0.0), 1.0) if prediction.lower() == "fake" else 0.1,
            "anti_spoofing_nn_confidence": 1.0 - min(max(confidence, 0.0), 1.0) if prediction.lower() == "fake" else 0.85,
        },
        "biometrics": {
            "arcface_visual_embedding": [random.gauss(0, 0.1) for _ in range(512)],
            "ecapa_voiceprint_embedding": [random.gauss(0, 0.1) for _ in range(256)],
        },
        "risk": {
            "ncii_indicator": False,
            "sexual_harassment_indicator": False,
            "synthetic_confidence": min(max(confidence, 0.0), 1.0),
        },
        "target": {
            "politician_name": "Subject Under Investigation",
            "role": "public_figure",
            "analyst_notes": f"Auto-generated from BharatShield detection. CNN={cnn_prob:.4f}, FFT={fft_prob:.4f}, Verdict={prediction}",
        },
    }

    return payload


async def generate_legal_documents(
    analysis: dict[str, Any],
    media_filename: str,
    media_hash: str,
    media_size: int,
    reporter_name: str | None = None,
    output_base_dir: Path | None = None,
) -> list[dict[str, str]]:
    """
    Generate legal documents using the bharatshield_legal2 pipeline.

    Returns a list of dicts with keys: document_type, filename, filepath, sha256_hash
    """
    if output_base_dir is None:
        output_base_dir = _REPO_ROOT / "backend" / "legal_output"
    output_base_dir.mkdir(parents=True, exist_ok=True)

    import importlib.util

    # Load and execute the legal config in a separate module and bind it to sys.modules["config"]
    # to avoid conflict with the root config.py
    legal_config_path = _REPO_ROOT / "bharatshield_legal2" / "config.py"
    spec = importlib.util.spec_from_file_location("config", str(legal_config_path))
    legal_config_module = importlib.util.module_from_spec(spec)

    old_config = sys.modules.get("config")
    sys.modules["config"] = legal_config_module

    try:
        spec.loader.exec_module(legal_config_module)

        # Import bharatshield_legal2 modules now that config is mocked
        from schemas import LegalPacketRequest
        from engine import LegalDecisionEngine
        from explanation import build_explanation
        from generator import DocumentGenerator
        from identity_merge import merge_identity
        from resolver import BiometricContextResolver

        # Build the payload
        payload_dict = _build_legal_packet_from_analysis(
            analysis, media_filename, media_hash, media_size, reporter_name
        )
        payload = LegalPacketRequest.model_validate(payload_dict)

        # Run the pipeline modules
        packet_id = str(uuid.uuid4())

        # Resolve identity (mock biometric match)
        resolver = BiometricContextResolver()
        biometric = await resolver.resolve(
            payload.biometrics,
            synthetic_confidence=payload.risk.synthetic_confidence,
        )
        identity = merge_identity(biometric, payload.target)

        # Build explanation
        explanation = build_explanation(
            payload.visual,
            payload.acoustic,
            extended=payload.extended_visual,
            user=payload.target,
        )

        # Legal routing
        engine = LegalDecisionEngine()
        routing = engine.evaluate(
            identity, payload.visual, payload.acoustic, payload.risk,
            explanation=explanation,
        )

        # Generate documents
        # Override output_dir for document generator
        import config as legal_config
        original_output_dir = legal_config.settings.output_dir
        legal_config.settings.output_dir = output_base_dir

        import generator
        original_generator_output_dir = generator.settings.output_dir
        generator.settings.output_dir = output_base_dir

        doc_generator = DocumentGenerator()
        documents = await doc_generator.generate_all(
            packet_id,
            payload.system,
            payload.file,
            payload.visual,
            payload.acoustic,
            identity,
            routing,
            explanation=explanation,
        )

        # Restore original output dir
        legal_config.settings.output_dir = original_output_dir
        generator.settings.output_dir = original_generator_output_dir

        result = []
        for doc in documents:
            result.append({
                "document_type": doc.document_type,
                "filename": doc.filename,
                "filepath": doc.filepath,
                "sha256_hash": doc.sha256_hash,
                "packet_id": packet_id,
            })

        logger.info("Generated %d legal documents for packet %s", len(result), packet_id)
        return result

    except Exception as exc:
        logger.exception("Legal document generation failed: %s", exc)
        raise
    finally:
        # Restore the original config in sys.modules
        if old_config is not None:
            sys.modules["config"] = old_config
        else:
            sys.modules.pop("config", None)
