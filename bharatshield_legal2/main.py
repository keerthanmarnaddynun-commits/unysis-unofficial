"""
BharatShield Legal Document Generation Pipeline — FastAPI application.
"""

from __future__ import annotations

import json
import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import quote

import httpx

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import settings
from dummy_data import build_dummy_payload_dict, build_dummy_request, dummy_metrics_json
from engine import LegalDecisionEngine
from explanation import build_explanation
from generator import DocumentGenerator
from identity_merge import merge_identity
from media_utils import apply_media_to_payload, ingest_upload, ingest_url
from reporting import AUTHORITY_DISPATCH_MATRIX, AuthorityReportingService
from resolver import BiometricContextResolver
from schemas import (
    LegalPacketRequest,
    LegalPacketResponse,
    ReportStatus,
    TargetRole,
)
from secure_log import EvidentiaryPacketCompiler

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

resolver = BiometricContextResolver()
decision_engine = LegalDecisionEngine()
doc_generator = DocumentGenerator()
packager = EvidentiaryPacketCompiler()
reporting_service = AuthorityReportingService()

templates = Jinja2Templates(directory=str(settings.base_dir / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await reporting_service.init_db()
    logger.info("%s v%s started", settings.app_name, settings.app_version)
    yield


_docs_url = "/docs" if settings.enable_api_docs else None
_redoc_url = "/redoc" if settings.enable_api_docs else None
_openapi_url = "/openapi.json" if settings.enable_api_docs else None

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Legal document generation pipeline for deepfake evidentiary packets (India 2026 framework)",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.mount("/static", StaticFiles(directory=str(settings.base_dir / "static")), name="static")


def verify_admin_key(x_admin_key: str | None = Header(default=None)) -> None:
    if x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Admin-Key header")


_ROLE_MAP = {
    "eci_official": TargetRole.ECI_OFFICIAL,
    "active_candidate": TargetRole.ACTIVE_CANDIDATE,
    "public_figure": TargetRole.PUBLIC_FIGURE,
}


async def _resolve_media_for_submit(
    media_mode: str,
    video_file: UploadFile | None,
    video_url: str | None,
):
    mode = (media_mode or "none").strip().lower()
    if mode == "none" or not mode:
        return None
    if mode == "file":
        if not video_file or not video_file.filename:
            raise HTTPException(400, "Please select an MP4 file to upload")
        raw = await video_file.read()
        try:
            return ingest_upload(raw, video_file.filename)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    if mode == "url":
        if not video_url or not video_url.strip():
            raise HTTPException(400, "Please enter a video URL")
        try:
            return await ingest_url(video_url)
        except httpx.HTTPError as exc:
            raise HTTPException(400, f"Could not download video from URL: {exc}") from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
    raise HTTPException(400, "Invalid media_mode; use file, url, or none")


def _list_packet_pdfs(packet_id: str) -> list[dict[str, str]]:
    docs_dir = settings.output_dir / packet_id / "documents"
    if not docs_dir.is_dir():
        return []
    items: list[dict[str, str]] = []
    for path in sorted(docs_dir.glob("*.pdf")):
        label = path.stem.replace("_", " ")
        items.append({"filename": path.name, "label": label})
    return items


def _success_redirect(result: LegalPacketResponse, *, admin: bool = False) -> RedirectResponse:
    target = result.identity.display_name or "Subject"
    base = "/admin/submit-success" if admin else "/submit/success"
    url = (
        f"{base}?packet_id={quote(result.packet_id)}"
        f"&report_id={quote(result.authority_report_id)}"
        f"&target={quote(target)}"
    )
    return RedirectResponse(url=url, status_code=303)


def _build_payload_from_form(
    politician_name: str,
    role: str,
    party_affiliation: str,
    constituency: str,
    analyst_notes: str,
    use_dummy: bool,
    metrics_json: str,
) -> LegalPacketRequest:
    selected_role = _ROLE_MAP.get(role, TargetRole.PUBLIC_FIGURE)
    if use_dummy or not metrics_json.strip():
        data = build_dummy_payload_dict(
            politician_name=politician_name.strip(),
            role=selected_role,
            party_affiliation=party_affiliation.strip() or None,
            constituency=constituency.strip() or None,
            analyst_notes=analyst_notes.strip() or None,
        )
    else:
        try:
            data = json.loads(metrics_json)
        except json.JSONDecodeError as exc:
            raise HTTPException(400, f"Invalid metrics JSON: {exc}") from exc
        data["target"] = {
            "politician_name": politician_name.strip(),
            "party_affiliation": party_affiliation.strip() or None,
            "constituency": constituency.strip() or None,
            "role": selected_role.value,
            "analyst_notes": analyst_notes.strip() or None,
        }
    return LegalPacketRequest.model_validate(data)


# --- Module 1: Ingestion API ---


@app.post("/api/v1/generate-legal-packet", response_model=LegalPacketResponse)
async def generate_legal_packet(payload: LegalPacketRequest) -> LegalPacketResponse:
    """
    Main pipeline: ingest forensic metrics → resolve identity → route legally →
    generate PDFs → package → queue authority report for admin.
    """
    packet_id = str(uuid.uuid4())
    logger.info("Processing legal packet %s for file %s", packet_id, payload.file.filename)

    biometric = await resolver.resolve(
        payload.biometrics,
        synthetic_confidence=payload.risk.synthetic_confidence,
    )
    identity = merge_identity(biometric, payload.target)
    explanation = build_explanation(
        payload.visual,
        payload.acoustic,
        extended=payload.extended_visual,
        user=payload.target,
    )
    routing = decision_engine.evaluate(
        identity,
        payload.visual,
        payload.acoustic,
        payload.risk,
        explanation=explanation,
    )
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
    package = await packager.compile(
        packet_id,
        payload.system,
        payload.file,
        identity,
        routing,
        documents,
        media_base64=payload.media_base64,
        actor=payload.system.analyst_id,
        explanation=explanation,
        merge_conflicts=identity.merge_conflicts,
    )
    sid = package.esakshya_metadata.get("sakshyaIdentificationNumber")
    authority_report = await reporting_service.create_report(
        packet_id=packet_id,
        case_type=routing.case_type,
        routing=routing,
        identity=identity,
        zip_sha256=package.zip_sha256,
        zip_path=package.zip_path,
        esakshya_sid=sid,
        explanation=explanation,
    )

    return LegalPacketResponse(
        success=True,
        packet_id=packet_id,
        identity=identity,
        routing=routing,
        explanation=explanation,
        package=package,
        authority_report_id=authority_report.id,
        message=(
            f"Evidentiary packet compiled. Authority report {authority_report.id} queued for admin review. "
            f"Review at /admin/reports/{authority_report.id}"
        ),
    )


@app.post("/api/v1/submit-case")
async def submit_case_with_media(
    politician_name: str = Form(...),
    role: str = Form("active_candidate"),
    party_affiliation: str = Form(""),
    constituency: str = Form(""),
    analyst_notes: str = Form(""),
    media_mode: str = Form("none"),
    video_url: str = Form(""),
    use_dummy_metrics: str = Form("1"),
    metrics_json: str = Form(""),
    video_file: UploadFile | None = File(None),
):
    """Multipart submit: politician details + optional MP4 file or video URL."""
    media = await _resolve_media_for_submit(media_mode, video_file, video_url)
    data = _build_payload_from_form(
        politician_name,
        role,
        party_affiliation,
        constituency,
        analyst_notes,
        use_dummy_metrics == "1",
        metrics_json,
    ).model_dump(mode="json")
    data = apply_media_to_payload(data, media)
    payload = LegalPacketRequest.model_validate(data)
    return await generate_legal_packet(payload)


@app.get("/api/v1/health")
async def health():
    return {"status": "ok", "version": settings.app_version, "qdrant_mock": settings.qdrant_mock}


@app.get("/api/v1/dummy-payload")
async def get_dummy_payload(
    politician_name: str = "Shri Demo Politician",
    role: TargetRole = TargetRole.ACTIVE_CANDIDATE,
):
    """Returns a complete sample JSON body using placeholder forensic values."""
    return build_dummy_payload_dict(politician_name=politician_name, role=role)


@app.post("/api/v1/demo/generate", response_model=LegalPacketResponse)
async def demo_generate_legal_packet(
    politician_name: str = "Shri Demo Politician",
    role: TargetRole = TargetRole.ACTIVE_CANDIDATE,
    party_affiliation: str | None = "Demo National Party",
    constituency: str | None = "Demo Lok Sabha Constituency",
):
    """One-click demo: runs full pipeline with dummy ML metrics and mock biometrics."""
    payload = build_dummy_request(
        politician_name=politician_name,
        role=role,
        party_affiliation=party_affiliation,
        constituency=constituency,
    )
    return await generate_legal_packet(payload)


@app.get("/api/v1/authority-channels")
async def authority_channels():
    """Reference: communication media required per case type."""
    return {
        case.value: channels
        for case, channels in AUTHORITY_DISPATCH_MATRIX.items()
    }


# --- Admin API ---


@app.get("/api/v1/admin/reports")
async def admin_list_reports(
    status: ReportStatus | None = None,
    _: None = Depends(verify_admin_key),
):
    reports = await reporting_service.list_reports(status=status)
    return {"reports": [r.model_dump(mode="json") for r in reports]}


@app.get("/api/v1/admin/reports/{report_id}")
async def admin_get_report(report_id: str, _: None = Depends(verify_admin_key)):
    report = await reporting_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    log = await reporting_service.get_dispatch_log(report_id)
    return {"report": report.model_dump(mode="json"), "dispatch_log": log}


@app.post("/api/v1/admin/reports/{report_id}/approve")
async def admin_approve_report(
    report_id: str,
    notes: str | None = None,
    _: None = Depends(verify_admin_key),
):
    updated = await reporting_service.update_status(
        report_id, ReportStatus.APPROVED, admin_notes=notes
    )
    if not updated:
        raise HTTPException(404, "Report not found")
    return {"success": True, "report": updated.model_dump(mode="json")}


@app.post("/api/v1/admin/reports/{report_id}/dispatch")
async def admin_dispatch_report(report_id: str, _: None = Depends(verify_admin_key)):
    result = await reporting_service.dispatch_report(report_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error", "Dispatch failed"))
    return result


@app.get("/api/v1/admin/reports/{report_id}/download")
async def admin_download_packet(report_id: str, _: None = Depends(verify_admin_key)):
    zip_path = await reporting_service.get_zip_path(report_id)
    if not zip_path:
        raise HTTPException(404, "Package not found")
    path = Path(zip_path)
    if not path.exists():
        raise HTTPException(404, "Zip file missing on disk")
    return FileResponse(path, filename=path.name, media_type="application/zip")


# --- Frontend (HTML UI) ---


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "app_name": settings.app_name,
            "active_nav": "home",
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    reports = await reporting_service.list_reports(limit=100)
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "reports": reports,
            "app_name": settings.app_name,
            "active_nav": "dashboard",
        },
    )


@app.get("/admin/new-case", response_class=HTMLResponse)
@app.get("/admin/create-case", response_class=HTMLResponse)
async def admin_new_case(request: Request):
    return templates.TemplateResponse(
        request,
        "admin/new_case.html",
        {
            "app_name": settings.app_name,
            "active_nav": "new_case",
            "default_politician": "Shri Demo Politician",
            "default_party": "Demo National Party",
            "default_constituency": "Demo Lok Sabha Constituency",
            "default_notes": (
                "Dummy run: lip-sync mismatch; inconsistent lighting and shadows on face."
            ),
        },
    )


@app.post("/admin/new-case")
async def admin_new_case_submit(
    politician_name: str = Form(...),
    role: str = Form("active_candidate"),
    party_affiliation: str = Form(""),
    constituency: str = Form(""),
    analyst_notes: str = Form(""),
    media_mode: str = Form("none"),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
):
    media = await _resolve_media_for_submit(media_mode, video_file, video_url)
    data = build_dummy_payload_dict(
        politician_name=politician_name.strip(),
        role=_ROLE_MAP.get(role, TargetRole.ACTIVE_CANDIDATE),
        party_affiliation=party_affiliation.strip() or None,
        constituency=constituency.strip() or None,
        analyst_notes=analyst_notes.strip() or None,
    )
    data = apply_media_to_payload(data, media)
    payload = LegalPacketRequest.model_validate(data)
    result = await generate_legal_packet(payload)
    return _success_redirect(result, admin=True)


@app.get("/admin/submit-success", response_class=HTMLResponse)
async def admin_submit_success(
    request: Request,
    packet_id: str,
    report_id: str,
    target: str = "Subject",
):
    return templates.TemplateResponse(
        request,
        "admin/submit_success.html",
        {
            "app_name": settings.app_name,
            "active_nav": "new_case",
            "packet_id": packet_id,
            "report_id": report_id,
            "target_name": target,
            "documents": _list_packet_pdfs(packet_id),
        },
    )


@app.get("/admin/reports/{report_id}", response_class=HTMLResponse)
async def admin_report_detail(request: Request, report_id: str):
    report = await reporting_service.get_report(report_id)
    if not report:
        raise HTTPException(404, "Report not found")
    dispatch_log = await reporting_service.get_dispatch_log(report_id)
    return templates.TemplateResponse(
        request,
        "admin/report_detail.html",
        {
            "report": report,
            "dispatch_log": dispatch_log,
            "admin_api_key": settings.admin_api_key,
            "explanation": report.explanation,
            "app_name": settings.app_name,
            "active_nav": "dashboard",
        },
    )


# --- Public submission UI ---


@app.get("/submit", response_class=HTMLResponse)
async def submit_form(request: Request):
    return templates.TemplateResponse(
        request,
        "submit.html",
        {
            "app_name": settings.app_name,
            "active_nav": "submit",
            "default_politician": "Shri Demo Politician",
            "default_party": "Demo National Party",
            "default_constituency": "Demo Lok Sabha Constituency",
            "default_notes": (
                "Dummy run: lip-sync mismatch; inconsistent lighting and shadows on face."
            ),
            "dummy_metrics_json": dummy_metrics_json(),
        },
    )


@app.post("/submit")
async def submit_packet(
    politician_name: str = Form(...),
    role: str = Form("public_figure"),
    party_affiliation: str = Form(""),
    constituency: str = Form(""),
    analyst_notes: str = Form(""),
    metrics_json: str = Form(""),
    use_dummy_metrics: str = Form(""),
    media_mode: str = Form("none"),
    video_url: str = Form(""),
    video_file: UploadFile | None = File(None),
):
    """HTML form handler with optional video upload or URL."""
    media = await _resolve_media_for_submit(media_mode, video_file, video_url)
    payload = _build_payload_from_form(
        politician_name,
        role,
        party_affiliation,
        constituency,
        analyst_notes,
        use_dummy_metrics == "1",
        metrics_json,
    )
    if media:
        data = apply_media_to_payload(payload.model_dump(mode="json"), media)
        payload = LegalPacketRequest.model_validate(data)
    result = await generate_legal_packet(payload)
    return _success_redirect(result, admin=False)


@app.get("/submit/success", response_class=HTMLResponse)
async def submit_success(
    request: Request,
    packet_id: str,
    report_id: str,
    target: str = "Subject",
):
    return templates.TemplateResponse(
        request,
        "submit_success.html",
        {
            "app_name": settings.app_name,
            "active_nav": "submit",
            "packet_id": packet_id,
            "report_id": report_id,
            "target_name": target,
            "documents": _list_packet_pdfs(packet_id),
        },
    )


@app.get("/files/{packet_id}/{filename}")
async def download_packet_pdf(packet_id: str, filename: str):
    safe_name = Path(filename).name
    if safe_name != filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    path = settings.output_dir / packet_id / "documents" / safe_name
    if not path.is_file():
        raise HTTPException(404, "Document not found")
    return FileResponse(path, filename=safe_name, media_type="application/pdf")


@app.post("/submit/demo")
async def submit_demo(
    politician_name: str = Form("Shri Demo Politician"),
    role: str = Form("active_candidate"),
):
    """One-click submit using only politician name + role; all metrics are dummy."""
    role_map = {
        "eci_official": TargetRole.ECI_OFFICIAL,
        "active_candidate": TargetRole.ACTIVE_CANDIDATE,
        "public_figure": TargetRole.PUBLIC_FIGURE,
    }
    payload = build_dummy_request(
        politician_name=politician_name.strip(),
        role=role_map.get(role, TargetRole.ACTIVE_CANDIDATE),
    )
    result = await generate_legal_packet(payload)
    return _success_redirect(result, admin=False)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=settings.debug)
