"""Authority reporting service and admin queue persistence."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import aiosqlite

from config import settings
from schemas import (
    AuthorityChannel,
    AuthorityReport,
    DeepfakeExplanation,
    LegalCaseType,
    LegalRoutingDecision,
    ReportStatus,
    ResolvedIdentity,
)

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


# Communication medium mapping per authority
AUTHORITY_DISPATCH_MATRIX: dict[LegalCaseType, list[dict[str, str]]] = {
    LegalCaseType.ECI_OFFICIAL: [
        {
            "channel": AuthorityChannel.ECI.value,
            "medium": "ECI Online Complaint Portal + registered post to Nirvachan Sadan",
            "endpoint": settings.eci_complaint_url,
            "contact": "complaints@eci.gov.in",
        },
        {
            "channel": AuthorityChannel.INTERMEDIARY_EMAIL.value,
            "medium": "Email to platform Grievance Officer (Rule 3 IT Rules 2026)",
            "endpoint": "grievance-officer@[platform-domain]",
            "contact": "Statutory 3-hour notice (PDF attached)",
        },
        {
            "channel": AuthorityChannel.ESakshya.value,
            "medium": "eSakshya web portal upload (MHA ICJS)",
            "endpoint": settings.esakshya_portal_url,
            "contact": "Court-ready bundle with 16-digit SID",
        },
        {
            "channel": AuthorityChannel.ADMIN_QUEUE.value,
            "medium": "Internal BharatShield Admin Panel review",
            "endpoint": "/admin/reports",
            "contact": "Supervisor approval before external dispatch",
        },
    ],
    LegalCaseType.ACTIVE_CANDIDATE: [
        {
            "channel": AuthorityChannel.ECI.value,
            "medium": "ECI Complaint — Section 123(4) RPA",
            "endpoint": settings.eci_complaint_url,
            "contact": "complaints@eci.gov.in",
        },
        {
            "channel": AuthorityChannel.LOCAL_POLICE_FIR.value,
            "medium": "CCTNS-compatible FIR draft → local police station / NCRP",
            "endpoint": settings.cybercrime_portal_url,
            "contact": "District Cyber Cell",
        },
        {
            "channel": AuthorityChannel.INTERMEDIARY_EMAIL.value,
            "medium": "Intermediary takedown email (3-hour window)",
            "endpoint": "grievance-officer@[platform]",
            "contact": "Automated notice dispatch",
        },
        {
            "channel": AuthorityChannel.ADMIN_QUEUE.value,
            "medium": "Admin panel supervisory review",
            "endpoint": "/admin/reports",
            "contact": "Internal queue",
        },
    ],
    LegalCaseType.GENERAL_PUBLIC_FIGURE: [
        {
            "channel": AuthorityChannel.CYBER_CRIME_NCRP.value,
            "medium": "National Cyber Crime Reporting Portal (NCRP)",
            "endpoint": settings.ncrp_api_hint,
            "contact": "Helpline 1930 / cybercrime.gov.in",
        },
        {
            "channel": AuthorityChannel.LOCAL_POLICE_FIR.value,
            "medium": "FIR at jurisdictional police station (CCTNS)",
            "endpoint": "https://cctns.nic.in/",
            "contact": "Station House Officer",
        },
        {
            "channel": AuthorityChannel.INTERMEDIARY_EMAIL.value,
            "medium": "Intermediary notice (2h or 3h per routing)",
            "endpoint": "grievance-officer@[platform]",
            "contact": "Platform compliance team",
        },
        {
            "channel": AuthorityChannel.ADMIN_QUEUE.value,
            "medium": "Admin panel",
            "endpoint": "/admin/reports",
            "contact": "Internal review",
        },
    ],
    LegalCaseType.UNRESOLVED_IDENTITY: [
        {
            "channel": AuthorityChannel.CYBER_CRIME_NCRP.value,
            "medium": "NCRP — identity-agnostic cyber complaint",
            "endpoint": settings.cybercrime_portal_url,
            "contact": "1930",
        },
        {
            "channel": AuthorityChannel.ADMIN_QUEUE.value,
            "medium": "Mandatory admin review before dispatch",
            "endpoint": "/admin/reports",
            "contact": "Forensic supervisor",
        },
    ],
}


class AuthorityReportingService:
    """Creates authority reports, persists to SQLite, supports admin workflow."""

    def __init__(self) -> None:
        self.db_path = settings.db_path

    async def _migrate(self, db: aiosqlite.Connection) -> None:
        async with db.execute("PRAGMA table_info(authority_reports)") as cur:
            cols = {row[1] for row in await cur.fetchall()}
        for col, typedef in (
            ("identity_source", "TEXT"),
            ("explanation_json", "TEXT"),
        ):
            if col not in cols:
                await db.execute(
                    f"ALTER TABLE authority_reports ADD COLUMN {col} {typedef}"
                )

    async def init_db(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS authority_reports (
                    id TEXT PRIMARY KEY,
                    packet_id TEXT NOT NULL,
                    case_type TEXT NOT NULL,
                    channels_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    target_name TEXT,
                    charges_summary TEXT,
                    zip_sha256 TEXT NOT NULL,
                    dispatch_instructions_json TEXT NOT NULL,
                    admin_notes TEXT,
                    zip_path TEXT,
                    esakshya_sid TEXT,
                    identity_source TEXT,
                    explanation_json TEXT
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS dispatch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    medium TEXT NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    FOREIGN KEY (report_id) REFERENCES authority_reports(id)
                )
                """
            )
            await self._migrate(db)
            await db.commit()

    def _channels_for_case(self, case_type: LegalCaseType) -> list[AuthorityChannel]:
        matrix = AUTHORITY_DISPATCH_MATRIX.get(case_type, [])
        return [AuthorityChannel(item["channel"]) for item in matrix]

    def _dispatch_instructions(self, case_type: LegalCaseType) -> dict[str, Any]:
        matrix = AUTHORITY_DISPATCH_MATRIX.get(case_type, [])
        return {
            "recommended_channels": matrix,
            "workflow": [
                "1. Admin reviews packet in /admin dashboard",
                "2. Supervisor approves report (POST /api/v1/admin/reports/{id}/approve)",
                "3. System dispatches to configured channels (POST .../dispatch)",
                "4. Track acknowledgements in dispatch_log",
            ],
            "manual_portals": {
                "eci": settings.eci_complaint_url,
                "ncrp": settings.cybercrime_portal_url,
                "esakshya": settings.esakshya_portal_url,
            },
        }

    async def create_report(
        self,
        packet_id: str,
        case_type: LegalCaseType,
        routing: LegalRoutingDecision,
        identity: ResolvedIdentity,
        zip_sha256: str,
        zip_path: str,
        esakshya_sid: str | None = None,
        explanation: DeepfakeExplanation | None = None,
    ) -> AuthorityReport:
        report_id = str(uuid.uuid4())
        now = datetime.now(IST)
        channels = self._channels_for_case(case_type)
        charges_summary = "; ".join(f"{c.statute} §{c.section}" for c in routing.charges)
        target = identity.display_name or (
            identity.profile.full_name if identity.profile else None
        )
        dispatch = self._dispatch_instructions(case_type)

        report = AuthorityReport(
            id=report_id,
            packet_id=packet_id,
            case_type=case_type,
            channels=channels,
            status=ReportStatus.PENDING_REVIEW,
            created_at=now,
            updated_at=now,
            target_name=target,
            charges_summary=charges_summary,
            zip_sha256=zip_sha256,
            dispatch_instructions=dispatch,
            identity_source=identity.identity_source.value,
            explanation=explanation,
        )

        async with aiosqlite.connect(self.db_path) as db:
            await self._migrate(db)
            await db.execute(
                """
                INSERT INTO authority_reports
                (id, packet_id, case_type, channels_json, status, created_at, updated_at,
                 target_name, charges_summary, zip_sha256, dispatch_instructions_json,
                 admin_notes, zip_path, esakshya_sid, identity_source, explanation_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.packet_id,
                    report.case_type.value,
                    json.dumps([c.value for c in report.channels]),
                    report.status.value,
                    report.created_at.isoformat(),
                    report.updated_at.isoformat(),
                    report.target_name,
                    report.charges_summary,
                    report.zip_sha256,
                    json.dumps(report.dispatch_instructions),
                    report.admin_notes,
                    zip_path,
                    esakshya_sid,
                    report.identity_source,
                    json.dumps(explanation.model_dump(mode="json")) if explanation else None,
                ),
            )
            for ch in dispatch.get("recommended_channels", []):
                await db.execute(
                    """
                    INSERT INTO dispatch_log (report_id, channel, medium, status, timestamp, details)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        report_id,
                        ch["channel"],
                        ch["medium"],
                        "queued",
                        now.isoformat(),
                        json.dumps({"endpoint": ch.get("endpoint"), "contact": ch.get("contact")}),
                    ),
                )
            await db.commit()

        logger.info("Authority report %s queued for admin review", report_id)
        return report

    async def list_reports(
        self,
        status: ReportStatus | None = None,
        limit: int = 50,
    ) -> list[AuthorityReport]:
        query = "SELECT * FROM authority_reports"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status.value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, params) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_report(dict(r)) for r in rows]

    async def get_report(self, report_id: str) -> AuthorityReport | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM authority_reports WHERE id = ?", (report_id,)
            ) as cursor:
                row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_report(dict(row))

    def _row_to_report(self, row: dict) -> AuthorityReport:
        expl_raw = row.get("explanation_json")
        explanation = None
        if expl_raw:
            explanation = DeepfakeExplanation.model_validate(json.loads(expl_raw))
        return AuthorityReport(
            id=row["id"],
            packet_id=row["packet_id"],
            case_type=LegalCaseType(row["case_type"]),
            channels=[AuthorityChannel(c) for c in json.loads(row["channels_json"])],
            status=ReportStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            target_name=row["target_name"],
            charges_summary=row["charges_summary"],
            zip_sha256=row["zip_sha256"],
            dispatch_instructions=json.loads(row["dispatch_instructions_json"]),
            admin_notes=row["admin_notes"],
            identity_source=row.get("identity_source"),
            explanation=explanation,
        )

    async def update_status(
        self,
        report_id: str,
        status: ReportStatus,
        admin_notes: str | None = None,
    ) -> AuthorityReport | None:
        report = await self.get_report(report_id)
        if not report:
            return None
        now = datetime.now(IST)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE authority_reports
                SET status = ?, updated_at = ?, admin_notes = COALESCE(?, admin_notes)
                WHERE id = ?
                """,
                (status.value, now.isoformat(), admin_notes, report_id),
            )
            await db.commit()
        report.status = status
        report.updated_at = now
        if admin_notes:
            report.admin_notes = admin_notes
        return report

    async def dispatch_report(self, report_id: str) -> dict[str, Any]:
        """
        Simulates multi-channel dispatch after admin approval.
        In production: integrate SMTP, ECI API, NCRP webhooks, etc.
        """
        report = await self.get_report(report_id)
        if not report:
            return {"success": False, "error": "Report not found"}
        if report.status not in (ReportStatus.APPROVED, ReportStatus.PENDING_REVIEW):
            if report.status == ReportStatus.DISPATCHED:
                return {"success": True, "message": "Already dispatched"}

        results: list[dict] = []
        now = datetime.now(IST)

        async with aiosqlite.connect(self.db_path) as db:
            for ch in report.dispatch_instructions.get("recommended_channels", []):
                channel_id = ch["channel"]
                # Simulate successful dispatch
                detail = {
                    "simulated": True,
                    "endpoint": ch.get("endpoint"),
                    "message": f"Notice queued via {ch.get('medium')}",
                }
                if channel_id == AuthorityChannel.INTERMEDIARY_EMAIL.value:
                    detail["smtp"] = "configured" if settings.smtp_host else "manual_email_required"
                results.append({"channel": channel_id, "status": "dispatched", "detail": detail})

                await db.execute(
                    """
                    UPDATE dispatch_log SET status = 'dispatched', timestamp = ?, details = ?
                    WHERE report_id = ? AND channel = ?
                    """,
                    (now.isoformat(), json.dumps(detail), report_id, channel_id),
                )
            await db.commit()

        await self.update_status(report_id, ReportStatus.DISPATCHED)
        return {"success": True, "report_id": report_id, "channels": results}

    async def get_dispatch_log(self, report_id: str) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM dispatch_log WHERE report_id = ? ORDER BY id",
                (report_id,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_zip_path(self, report_id: str) -> str | None:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT zip_path FROM authority_reports WHERE id = ?", (report_id,)
            ) as cursor:
                row = await cursor.fetchone()
        return row[0] if row else None
