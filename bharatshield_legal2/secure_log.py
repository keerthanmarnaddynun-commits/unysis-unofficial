"""Module 5: Cryptographic packaging, audit trail, and eSakshya compliance."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from config import settings
from schemas import (
    AuditLogEntry,
    DeepfakeExplanation,
    EvidentiaryPackage,
    GeneratedDocument,
    LegalRoutingDecision,
    ResolvedIdentity,
    SystemMetadata,
    FileMetadata,
)

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _generate_sid() -> str:
    """16-digit Sakshya Identification Number (SID) for eSakshya."""
    return "".join(str(random.randint(0, 9)) for _ in range(16))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class EvidentiaryPacketCompiler:
    """Compiles zip package, JSON-LD audit log, and eSakshya metadata."""

    def __init__(self) -> None:
        self.audit_dir = settings.audit_dir

    def _write_media(
        self,
        packet_dir: Path,
        file_meta: FileMetadata,
        media_base64: str | None,
    ) -> Path | None:
        if not media_base64:
            placeholder = packet_dir / file_meta.filename
            placeholder.write_text(
                f"[Placeholder for original media — SHA-256: {file_meta.sha256_hash}]",
                encoding="utf-8",
            )
            return placeholder
        try:
            raw = base64.b64decode(media_base64)
            media_path = packet_dir / file_meta.filename
            media_path.write_bytes(raw)
            return media_path
        except Exception as exc:
            logger.error("Failed to decode media: %s", exc)
            return None

    def build_esakshya_payload(
        self,
        sid: str,
        packet_id: str,
        zip_sha256: str,
        system: SystemMetadata,
        file: FileMetadata,
        identity: ResolvedIdentity,
        routing: LegalRoutingDecision,
        documents: list[GeneratedDocument],
        explanation: DeepfakeExplanation | None = None,
    ) -> dict[str, Any]:
        """Metadata mapped to eSakshya court-ready schema."""
        now = datetime.now(IST)
        return {
            "@context": {
                "@vocab": "https://icjs.gov.in/esakshya/vocab#",
                "schema": "https://schema.org/",
            },
            "@type": "ElectronicEvidenceBundle",
            "sakshyaIdentificationNumber": sid,
            "portalUrl": settings.esakshya_portal_url,
            "packetId": packet_id,
            "submissionTimestampIST": now.isoformat(),
            "primaryEvidenceHashSHA256": file.sha256_hash,
            "bundleHashSHA256": zip_sha256,
            "declarant": {
                "analystId": system.analyst_id,
                "workstationSerial": system.workstation_serial_number,
                "terminalMac": system.terminal_mac_address,
            },
            "subject": {
                "identified": identity.matched,
                "displayName": identity.display_name
                or (identity.profile.full_name if identity.profile else None),
                "fullName": identity.profile.full_name if identity.profile else None,
                "identityId": identity.identity_id,
                "identitySource": identity.identity_source.value,
                "biometricMatched": identity.biometric_matched,
            },
            "forensicNarrative": explanation.model_dump(mode="json") if explanation else None,
            "legalRouting": {
                "caseType": routing.case_type.value,
                "takedownHours": routing.takedown_hours,
                "charges": [
                    {"statute": c.statute, "section": c.section, "description": c.description}
                    for c in routing.charges
                ],
            },
            "certificates": [
                {"type": d.document_type, "filename": d.filename, "sha256": d.sha256_hash}
                for d in documents
            ],
            "uploadInstructions": (
                "Login to eSakshya at https://icjs.gov.in/esakshya/ → New Submission → "
                "Enter SID → Upload evidentiary zip → Attach JSON metadata."
            ),
        }

    async def compile(
        self,
        packet_id: str,
        system: SystemMetadata,
        file: FileMetadata,
        identity: ResolvedIdentity,
        routing: LegalRoutingDecision,
        documents: list[GeneratedDocument],
        media_base64: str | None = None,
        actor: str = "system",
        explanation: DeepfakeExplanation | None = None,
        merge_conflicts: list[str] | None = None,
    ) -> EvidentiaryPackage:
        packet_dir = settings.output_dir / packet_id
        packet_dir.mkdir(parents=True, exist_ok=True)

        media_path = self._write_media(packet_dir, file, media_base64)
        zip_path = packet_dir / f"evidentiary_packet_{packet_id}.zip"
        sid = _generate_sid()

        audit_entries: list[AuditLogEntry] = [
            AuditLogEntry(
                timestamp=datetime.now(IST),
                action="packet_compilation_started",
                actor=actor,
                file_hash=file.sha256_hash,
                details={
                    "packet_id": packet_id,
                    "merge_conflicts": merge_conflicts or [],
                },
            )
        ]

        explanation_path: Path | None = None
        if explanation:
            explanation_path = packet_dir / "explanation.json"
            explanation_path.write_text(
                json.dumps(explanation.model_dump(mode="json"), indent=2),
                encoding="utf-8",
            )

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if media_path and media_path.exists():
                zf.write(media_path, arcname=f"original_media/{media_path.name}")
            for doc in documents:
                p = Path(doc.filepath)
                if p.exists():
                    zf.write(p, arcname=f"legal_documents/{doc.filename}")

            manifest = {
                "packet_id": packet_id,
                "sid": sid,
                "created": datetime.now(IST).isoformat(),
                "documents": [d.model_dump() for d in documents],
            }
            manifest_str = json.dumps(manifest, indent=2, default=str)
            zf.writestr("manifest.json", manifest_str)
            if explanation_path and explanation_path.exists():
                zf.write(explanation_path, arcname="forensic/explanation.json")

        zip_sha256 = _sha256_file(zip_path)
        audit_entries.append(
            AuditLogEntry(
                timestamp=datetime.now(IST),
                action="zip_sealed",
                actor=actor,
                file_hash=zip_sha256,
                details={"zip_path": str(zip_path)},
            )
        )

        # JSON-LD immutable audit chain
        audit_log_path = self.audit_dir / f"{packet_id}_audit.jsonld"
        audit_doc = {
            "@context": {
                "@vocab": "https://bharatshield.local/audit#",
                "schema": "https://schema.org/",
            },
            "@type": "ChainOfCustodyLog",
            "packetId": packet_id,
            "entries": [e.model_dump(mode="json") for e in audit_entries],
            "finalPackageHash": zip_sha256,
        }
        audit_log_path.write_text(json.dumps(audit_doc, indent=2, default=str), encoding="utf-8")

        esakshya = self.build_esakshya_payload(
            sid, packet_id, zip_sha256, system, file, identity, routing, documents, explanation
        )
        esakshya_path = packet_dir / "esakshya_metadata.json"
        esakshya_path.write_text(json.dumps(esakshya, indent=2), encoding="utf-8")

        with zipfile.ZipFile(zip_path, "a", zipfile.ZIP_DEFLATED) as zf:
            zf.write(esakshya_path, arcname="esakshya_metadata.json")
            zf.write(audit_log_path, arcname=f"audit/{audit_log_path.name}")

        # Re-hash after adding metadata
        zip_sha256 = _sha256_file(zip_path)
        esakshya["bundleHashSHA256"] = zip_sha256

        return EvidentiaryPackage(
            zip_path=str(zip_path),
            zip_sha256=zip_sha256,
            audit_log_path=str(audit_log_path),
            documents=documents,
            esakshya_metadata=esakshya,
        )
