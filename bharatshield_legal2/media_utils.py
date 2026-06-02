"""Ingest video evidence from MP4 upload or URL."""

from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from config import settings

ALLOWED_EXTENSIONS = {".mp4"}
URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)


@dataclass
class IngestedMedia:
    filename: str
    file_size_bytes: int
    sha256_hash: str
    media_base64: str
    source: str  # "upload" | "url"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def ingest_upload(file_bytes: bytes, original_filename: str) -> IngestedMedia:
    if len(file_bytes) > settings.max_upload_bytes:
        raise ValueError(
            f"File exceeds maximum size of {settings.max_upload_bytes // (1024*1024)} MB"
        )
    ext = Path(original_filename).suffix.lower() or ".mp4"
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError("Only MP4 video files are supported")
    if len(file_bytes) < 32:
        raise ValueError("Uploaded file is empty or too small")

    safe_name = Path(original_filename).name
    if not safe_name.lower().endswith(".mp4"):
        safe_name = f"{Path(safe_name).stem}.mp4"

    return IngestedMedia(
        filename=safe_name,
        file_size_bytes=len(file_bytes),
        sha256_hash=_sha256_bytes(file_bytes),
        media_base64=base64.b64encode(file_bytes).decode("ascii"),
        source="upload",
    )


async def ingest_url(video_url: str) -> IngestedMedia:
    url = video_url.strip()
    if not URL_PATTERN.match(url):
        raise ValueError("Video URL must start with http:// or https://")

    parsed = urlparse(url)
    path_name = Path(parsed.path).name
    if path_name and path_name.lower().endswith(".mp4"):
        filename = path_name
    else:
        filename = "evidence_from_url.mp4"

    async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        content_type = (resp.headers.get("content-type") or "").lower()
        if "video" not in content_type and "octet-stream" not in content_type:
            # Allow if URL path ends with .mp4
            if not filename.lower().endswith(".mp4"):
                raise ValueError(
                    "URL does not appear to point to a video file (expected video/mp4)"
                )
        data = resp.content

    return ingest_upload(data, filename)


def apply_media_to_payload(data: dict, media: IngestedMedia | None) -> dict:
    """Update legal packet dict with real file metadata and base64 media."""
    if media is None:
        return data
    data = dict(data)
    data["file"] = {
        **data.get("file", {}),
        "filename": media.filename,
        "file_size_bytes": media.file_size_bytes,
        "container_format": "mp4",
        "sha256_hash": media.sha256_hash,
    }
    data["media_base64"] = media.media_base64
    return data
