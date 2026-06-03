"""Application configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "BharatShield Legal Document Pipeline"
    app_version: str = "1.0.0"
    debug: bool = False

    # Paths
    base_dir: Path = Path(__file__).resolve().parent
    output_dir: Path = base_dir / "output"
    uploads_dir: Path = base_dir / "uploads"
    audit_dir: Path = base_dir / "audit"
    db_path: Path = base_dir / "data" / "reports.db"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None
    qdrant_face_collection: str = "national_public_figures_face"
    qdrant_voice_collection: str = "national_public_figures_voice"
    similarity_threshold: float = 0.75
    qdrant_mock: bool = True  # Use in-memory mock when Qdrant unavailable

    # Identity fusion (SELFI)
    fusion_identity_weight: float = 0.6
    fusion_visual_weight: float = 0.4

    # Admin
    admin_api_key: str = "change-me-in-production"
    admin_username: str = "admin"

    # Authority reporting (SMTP optional)
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@bharatshield.local"

    # Portal endpoints (metadata / dispatch targets)
    esakshya_portal_url: str = "https://icjs.gov.in/esakshya/"
    eci_complaint_url: str = "https://eci.gov.in/contact-eci"
    cybercrime_portal_url: str = "https://cybercrime.gov.in/Webform/Index.aspx"
    ncrp_api_hint: str = "https://cybercrime.gov.in/Webform/CrimeReport.aspx"

    # Deepfake explanation thresholds
    lip_sync_warn_ms: float = 80.0
    spatial_cnn_warn: float = 0.7
    tts_synthetic_warn: float = 0.6
    pitch_mismatch_warn: float = 0.3
    anti_spoofing_low_warn: float = 0.3
    face_mesh_variance_warn: float = 0.05
    extended_visual_warn: float = 0.55

    # Media upload
    max_upload_bytes: int = 100 * 1024 * 1024  # 100 MB
    enable_api_docs: bool = False


settings = Settings()

# Ensure runtime directories exist
for _d in (settings.output_dir, settings.uploads_dir, settings.audit_dir, settings.db_path.parent):
    _d.mkdir(parents=True, exist_ok=True)
