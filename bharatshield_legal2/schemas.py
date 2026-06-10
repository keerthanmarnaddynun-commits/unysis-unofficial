"""Pydantic v2 schemas for legal document generation pipeline."""

from datetime import datetime
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# --- Ingestion payload (Module 1) ---


class SystemMetadata(BaseModel):
    ingestion_timestamp: datetime
    analyst_id: str = Field(..., min_length=1, max_length=128)
    terminal_mac_address: str = Field(..., pattern=r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
    workstation_serial_number: str = Field(..., min_length=1, max_length=64)


class FileMetadata(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    file_size_bytes: int = Field(..., gt=0)
    container_format: str = Field(..., min_length=1, max_length=32)
    sha256_hash: str = Field(..., pattern=r"^[a-fA-F0-9]{64}$")

    @field_validator("sha256_hash")
    @classmethod
    def normalize_hash(cls, v: str) -> str:
        return v.lower()


class VisualForensics(BaseModel):
    spatial_cnn_manipulation_probability: float = Field(..., ge=0.0, le=1.0)
    face_mesh_landmark_variance: float = Field(..., ge=0.0)
    lip_sync_alignment_error_ms: float = Field(..., ge=0.0)


class AcousticForensics(BaseModel):
    tts_synthetic_probability: float = Field(..., ge=0.0, le=1.0)
    spectrogram_pitch_mismatch_ratio: float = Field(..., ge=0.0, le=1.0)
    anti_spoofing_nn_confidence: float = Field(..., ge=0.0, le=1.0)


class BiometricEmbeddings(BaseModel):
    arcface_visual_embedding: Annotated[list[float], Field(min_length=512, max_length=512)]
    ecapa_voiceprint_embedding: Annotated[list[float], Field(min_length=256, max_length=256)]

    @field_validator("arcface_visual_embedding", "ecapa_voiceprint_embedding")
    @classmethod
    def validate_finite(cls, v: list[float]) -> list[float]:
        if not all(isinstance(x, (int, float)) for x in v):
            raise ValueError("Embeddings must be numeric")
        return [float(x) for x in v]


class ExtendedVisualForensics(BaseModel):
    """Optional scores from extended ML pipeline (shadows, color, temporal)."""

    illumination_inconsistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    shadow_geometry_inconsistency_score: float | None = Field(default=None, ge=0.0, le=1.0)
    color_grading_anomaly_score: float | None = Field(default=None, ge=0.0, le=1.0)
    temporal_flicker_score: float | None = Field(default=None, ge=0.0, le=1.0)
    facial_boundary_artifact_score: float | None = Field(default=None, ge=0.0, le=1.0)


class TargetRole(str, Enum):
    ECI_OFFICIAL = "eci_official"
    ACTIVE_CANDIDATE = "active_candidate"
    PUBLIC_FIGURE = "public_figure"


class UserTargetInput(BaseModel):
    """User-declared politician / public figure (hybrid with biometrics)."""

    politician_name: str = Field(..., min_length=1, max_length=256)
    party_affiliation: str | None = None
    constituency: str | None = None
    gender: str | None = None
    role: TargetRole | None = Field(
        default=None,
        description="When set, drives legal routing (Case A/B/C).",
    )
    is_eci_official: bool | None = None
    active_candidacy_mcc: bool | None = None
    analyst_notes: str | None = Field(
        default=None,
        max_length=4000,
        description="Free-text forensic observations from analyst.",
    )


class RiskIndicators(BaseModel):
    """Optional flags for NCII / sexual harassment routing (Case C)."""
    ncii_indicator: bool = False
    sexual_harassment_indicator: bool = False
    synthetic_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LegalPacketRequest(BaseModel):
    system: SystemMetadata
    file: FileMetadata
    visual: VisualForensics
    acoustic: AcousticForensics
    biometrics: BiometricEmbeddings
    risk: RiskIndicators = Field(default_factory=RiskIndicators)
    target: UserTargetInput | None = Field(
        default=None,
        description="Optional user-specified politician name and role for hybrid routing.",
    )
    extended_visual: ExtendedVisualForensics | None = Field(
        default=None,
        description="Optional extended ML visual scores (shadows, color, etc.).",
    )
    media_base64: str | None = Field(
        default=None,
        description="Optional base64-encoded original media for packaging",
    )


# --- Identity resolution (Module 2) ---


class ProfileDetails(BaseModel):
    full_name: str
    aadhaar_masked: str
    gender: str


class ElectoralContext(BaseModel):
    party_affiliation: str | None = None
    active_candidacy_mcc: bool = False
    constituency: str | None = None
    role: str | None = None


class IdentitySource(str, Enum):
    BIOMETRIC = "biometric"
    USER_OVERRIDE = "user_override"
    HYBRID = "hybrid"


class ResolvedIdentity(BaseModel):
    matched: bool
    cosine_similarity_face: float | None = None
    cosine_similarity_voice: float | None = None
    fused_similarity: float | None = None
    profile: ProfileDetails | None = None
    electoral: ElectoralContext | None = None
    is_eci_official: bool = False
    identity_id: str | None = None
    display_name: str | None = None
    identity_source: IdentitySource = IdentitySource.BIOMETRIC
    biometric_matched: bool = False
    merge_conflicts: list[str] = Field(default_factory=list)


# --- Deepfake explanation ---


class ExplanationSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExplanationFinding(BaseModel):
    category: str
    severity: ExplanationSeverity
    plain_language: str
    metric_ref: str | None = None
    value: str | None = None
    source: str = "rule_engine"


class DeepfakeExplanation(BaseModel):
    summary: str
    findings: list[ExplanationFinding] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


# --- Legal routing (Module 3) ---


class LegalCaseType(str, Enum):
    ECI_OFFICIAL = "case_a_eci_official"
    ACTIVE_CANDIDATE = "case_b_active_candidate"
    GENERAL_PUBLIC_FIGURE = "case_c_general_public"
    UNRESOLVED_IDENTITY = "case_unresolved"


class StatutoryCharge(BaseModel):
    statute: str
    section: str
    description: str


class LegalRoutingDecision(BaseModel):
    case_type: LegalCaseType
    charges: list[StatutoryCharge]
    documents_to_generate: list[str]
    takedown_hours: int = 3
    routing_rationale: str


# --- Document generation output ---


class GeneratedDocument(BaseModel):
    document_type: str
    filename: str
    filepath: str
    sha256_hash: str


# --- Packaging (Module 5) ---


class AuditLogEntry(BaseModel):
    timestamp: datetime
    action: str
    actor: str
    file_hash: str | None = None
    details: dict = Field(default_factory=dict)


class EvidentiaryPackage(BaseModel):
    zip_path: str
    zip_sha256: str
    audit_log_path: str
    documents: list[GeneratedDocument]
    esakshya_metadata: dict


# --- Authority reporting ---


class AuthorityChannel(str, Enum):
    ECI = "election_commission_of_india"
    CYBER_CRIME_NCRP = "national_cyber_crime_reporting_portal"
    LOCAL_POLICE_FIR = "local_police_cctns"
    INTERMEDIARY_EMAIL = "intermediary_platform_notice"
    ESakshya = "esakshya_portal_upload"
    ADMIN_QUEUE = "internal_admin_review"


class ReportStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"


class AuthorityReport(BaseModel):
    id: str
    packet_id: str
    case_type: LegalCaseType
    channels: list[AuthorityChannel]
    status: ReportStatus
    created_at: datetime
    updated_at: datetime
    target_name: str | None
    charges_summary: str
    zip_sha256: str
    dispatch_instructions: dict
    admin_notes: str | None = None
    identity_source: str | None = None
    explanation: DeepfakeExplanation | None = None


class LegalPacketResponse(BaseModel):
    success: bool
    packet_id: str
    identity: ResolvedIdentity
    routing: LegalRoutingDecision
    explanation: DeepfakeExplanation
    package: EvidentiaryPackage
    authority_report_id: str
    message: str
