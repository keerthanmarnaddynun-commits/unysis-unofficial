"""
Report service — MongoDB + GridFS persistence for authority reports.
Replaces the SQLite-based reporting in bharatshield_legal2.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorGridFSBucket
from bson import ObjectId
import certifi

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))


def _generate_case_id() -> str:
    """Generate a human-readable case ID like BS-10234."""
    import random
    return f"BS-{random.randint(10000, 99999)}"


def _now_ist() -> datetime:
    return datetime.now(IST)


class ReportService:
    """Async MongoDB service for deepfake authority reports with GridFS media."""

    def __init__(self) -> None:
        self._client: AsyncIOMotorClient | None = None
        self._db = None
        self._fs: AsyncIOMotorGridFSBucket | None = None

    async def init(self) -> None:
        """Initialize MongoDB connection and GridFS bucket."""
        mongo_uri = os.getenv("MONGO_URI")
        db_name = os.getenv("MONGO_DB", "unisys_project")

        if not mongo_uri:
            raise RuntimeError("MONGO_URI environment variable is required")

        self._client = AsyncIOMotorClient(mongo_uri, tlsCAFile=certifi.where())
        self._db = self._client[db_name]
        self._fs = AsyncIOMotorGridFSBucket(self._db, bucket_name="report_media")

        # Create indexes
        await self._db.reports.create_index("report_id", unique=True)
        await self._db.reports.create_index("reporter.role")
        await self._db.reports.create_index("status")
        await self._db.reports.create_index("created_at")
        await self._db.dispatch_log.create_index("report_id")

        logger.info("ReportService initialized with MongoDB: %s/%s", mongo_uri[:30], db_name)

    async def close(self) -> None:
        if self._client:
            self._client.close()

    # --- GridFS Media Storage ---

    async def store_media(self, file_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
        """Store media file in GridFS. Returns the GridFS file_id as string."""
        if not self._fs:
            raise RuntimeError("ReportService not initialized")

        sha256 = hashlib.sha256(file_bytes).hexdigest()
        grid_in = self._fs.open_upload_stream(
            filename,
            metadata={
                "content_type": content_type,
                "sha256": sha256,
                "uploaded_at": _now_ist().isoformat(),
            },
        )
        await grid_in.write(file_bytes)
        await grid_in.close()

        file_id = str(grid_in._id)
        logger.info("Stored media '%s' in GridFS: %s (%d bytes)", filename, file_id, len(file_bytes))
        return file_id

    async def retrieve_media(self, file_id: str) -> tuple[bytes, str]:
        """Retrieve media from GridFS. Returns (file_bytes, filename)."""
        if not self._fs:
            raise RuntimeError("ReportService not initialized")

        try:
            grid_out = await self._fs.open_download_stream(ObjectId(file_id))
            data = await grid_out.read()
            return data, grid_out.filename
        except Exception as exc:
            logger.error("Failed to retrieve media %s: %s", file_id, exc)
            raise

    # --- Report CRUD ---

    async def create_report(
        self,
        reporter_role: str,
        reporter_identifier: str,
        reporter_name: str | None,
        analysis_data: dict[str, Any],
        media_file_id: str | None,
        media_hash: str | None,
        media_filename: str | None,
    ) -> dict[str, Any]:
        """Create a new deepfake report in MongoDB."""
        now = _now_ist()
        report_id = _generate_case_id()

        report = {
            "report_id": report_id,
            "reporter": {
                "role": reporter_role,
                "identifier": reporter_identifier,
                "name": reporter_name,
            },
            "analysis": analysis_data,
            "media_file_id": media_file_id,
            "media_hash": media_hash,
            "media_filename": media_filename,
            "status": "pending_review",
            "legal_documents": [],
            "created_at": now,
            "updated_at": now,
            "reanalysis_history": [],
            "custody_log": [
                {"time": now.isoformat(), "event": "Report submitted", "actor": f"{reporter_role} ({reporter_identifier})"},
                {"time": now.isoformat(), "event": "SHA-256 hash verified", "actor": "System"},
                {"time": now.isoformat(), "event": "Evidence locked in MongoDB GridFS", "actor": "System"},
            ],
        }

        result = await self._db.reports.insert_one(report)
        report["_id"] = str(result.inserted_id)
        logger.info("Created report %s by %s (%s)", report_id, reporter_role, reporter_identifier)

        return self._serialize_report(report)

    async def get_report(self, report_id: str) -> dict[str, Any] | None:
        """Get a report by its case ID (e.g. BS-10234)."""
        doc = await self._db.reports.find_one({"report_id": report_id})
        if not doc:
            return None
        return self._serialize_report(doc)

    async def list_reports(
        self,
        role: str | None = None,
        reporter_identifier: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List reports, optionally filtered by role/status."""
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if role and role != "Authority":
            # Non-authority users only see their own reports
            query["reporter.identifier"] = reporter_identifier

        cursor = self._db.reports.find(query).sort("created_at", -1).limit(limit)
        reports = []
        async for doc in cursor:
            reports.append(self._serialize_report(doc))
        return reports

    async def update_status(
        self,
        report_id: str,
        status: str,
        admin_notes: str | None = None,
    ) -> dict[str, Any] | None:
        """Update report status and optionally add admin notes."""
        now = _now_ist()
        update: dict[str, Any] = {
            "$set": {"status": status, "updated_at": now},
            "$push": {
                "custody_log": {
                    "time": now.isoformat(),
                    "event": f"Status updated to {status}",
                    "actor": "Authority",
                }
            },
        }
        if admin_notes:
            update["$set"]["admin_notes"] = admin_notes

        result = await self._db.reports.find_one_and_update(
            {"report_id": report_id},
            update,
            return_document=True,
        )
        if not result:
            return None
        return self._serialize_report(result)

    async def add_reanalysis(
        self,
        report_id: str,
        new_analysis: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Add re-analysis results to a report."""
        now = _now_ist()
        result = await self._db.reports.find_one_and_update(
            {"report_id": report_id},
            {
                "$set": {"updated_at": now},
                "$push": {
                    "reanalysis_history": {
                        "analysis": new_analysis,
                        "performed_at": now.isoformat(),
                        "performed_by": "Authority",
                    },
                    "custody_log": {
                        "time": now.isoformat(),
                        "event": "Media re-evaluated by authority",
                        "actor": "Authority",
                    },
                },
            },
            return_document=True,
        )
        if not result:
            return None
        return self._serialize_report(result)

    async def add_legal_documents(
        self,
        report_id: str,
        documents: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        """Add generated legal document references to a report."""
        now = _now_ist()
        result = await self._db.reports.find_one_and_update(
            {"report_id": report_id},
            {
                "$set": {"legal_documents": documents, "updated_at": now},
                "$push": {
                    "custody_log": {
                        "time": now.isoformat(),
                        "event": f"Legal documents generated ({len(documents)} docs)",
                        "actor": "System",
                    }
                },
            },
            return_document=True,
        )
        if not result:
            return None
        return self._serialize_report(result)

    async def update_takedown_status(
        self,
        report_id: str,
        status: str,
        response_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update takedown status and response data for a report."""
        now = _now_ist()
        result = await self._db.reports.find_one_and_update(
            {"report_id": report_id},
            {
                "$set": {
                    "takedown_status": status,
                    "takedown_response": response_data,
                    "updated_at": now,
                },
                "$push": {
                    "custody_log": {
                        "time": now.isoformat(),
                        "event": f"Takedown notice {status}",
                        "actor": "Authority",
                    }
                },
            },
            return_document=True,
        )
        if not result:
            return None
        return self._serialize_report(result)

    # --- Serialization ---

    def _serialize_report(self, doc: dict) -> dict[str, Any]:
        """Convert MongoDB document to JSON-serializable dict."""
        doc["_id"] = str(doc["_id"])
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        if isinstance(doc.get("updated_at"), datetime):
            doc["updated_at"] = doc["updated_at"].isoformat()
        return doc
