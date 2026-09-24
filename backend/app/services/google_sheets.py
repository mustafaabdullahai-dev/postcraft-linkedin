"""Google Sheets audit logging + guaranteed local JSONL fallback."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SHEET_HEADERS = [
    "Record ID",
    "Timestamp",
    "User Query",
    "Topic",
    "Audience",
    "Content Angle",
    "Generated Post",
    "Final Edited Post",
    "Hashtags",
    "Image Prompt",
    "Image URL",
    "AI Model",
    "Image Model",
    "Validation Status",
    "Review Status",
    "Approval Status",
    "LinkedIn Status",
    "LinkedIn Post ID",
    "Error",
    "Updated At",
]


class LocalAuditLogger:
    """Always writes a durable JSONL record — independent of Google Sheets."""

    def __init__(self, path: str | Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: Dict[str, Any]) -> None:
        line = json.dumps(record, default=str, ensure_ascii=False)
        with open(self._path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def update(self, record_id: str, data: Dict[str, Any]) -> None:
        # JSONL is append-only by design; the same id is emitted with a later
        # `updated_at`, making the full history indexable.
        self.append({"record_id": record_id, "update": True, **data})


class GoogleSheetsService:
    """Appends/updates audit rows. Dry-run performs a local JSONL write.

    When GOOGLE_SERVICE_ACCOUNT_JSON + GOOGLE_SHEET_ID are configured it
    writes real rows through the Sheets API.
    """

    def __init__(self, settings: Settings, audit_path: str | Path):
        self._settings = settings
        self._dry_run = settings.google_sheets_dry_run
        self._sheet_id = settings.google_sheet_id
        self._credentials = settings.google_service_account_json
        self._local = LocalAuditLogger(audit_path)

    def mode(self) -> str:
        return "dry_run" if self._dry_run else "google_sheets"

    def _row(self, record: Dict[str, Any]) -> List[str]:
        now = datetime.now(timezone.utc).isoformat()
        return [
            record.get("record_id", ""),
            record.get("timestamp", now),
            record.get("user_query", ""),
            record.get("topic", ""),
            record.get("audience", ""),
            record.get("content_angle", ""),
            record.get("generated_post", ""),
            record.get("final_post", ""),
            " ".join(record.get("hashtags", [])),
            record.get("image_prompt", ""),
            record.get("image_url", ""),
            record.get("text_model", ""),
            record.get("image_provider", ""),
            record.get("validation_status", ""),
            record.get("review_status", ""),
            record.get("approval_status", ""),
            record.get("publishing_status", ""),
            record.get("linkedin_post_id", ""),
            record.get("error", ""),
            record.get("updated_at", now),
        ]

    async def append_record(self, record: Dict[str, Any], state_id: Optional[str] = None) -> str:
        record_id = record.get("record_id", state_id or "")
        meta = {
            **record,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "GENERATED",
        }

        self._local.append(meta)
        if self._dry_run:
            logger.info("sheets dry-run append", record_id=record_id)
            return "LOGGED_LOCAL_DRYRUN"

        try:
            await self._append_remote(meta)
            return "LOGGED"
        except Exception as exc:  # noqa: BLE001
            logger.error("google sheets append failed", error=str(exc))
            raise

    async def update_record(self, record_id: str, data: Dict[str, Any]) -> str:
        meta = {**data, "record_id": record_id, "event": "UPDATE",
                "updated_at": datetime.now(timezone.utc).isoformat()}
        self._local.update(record_id, meta)
        if self._dry_run:
            logger.info("sheets dry-run update", record_id=record_id)
            return "LOGGED_LOCAL_DRYRUN"
        try:
            await self._remote_update_row(record_id, meta)
            return "LOGGED"
        except Exception as exc:  # noqa: BLE001
            logger.error("google sheets update failed", error=str(exc))
            raise

    # ── Google Sheets internals ────────────────────────────────
    def _service(self):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds_json = self._resolve_credentials()
        creds = service_account.Credentials.from_service_account_info(
            creds_json,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        return build("sheets", "v4", credentials=creds)

    def _resolve_credentials(self) -> Dict[str, Any]:
        value = self._credentials.strip()
        if value.startswith("file:"):
            path = value.split("file:", 1)[1]
            return json.loads(Path(path).read_text(encoding="utf-8"))
        return json.loads(value)

    async def _append_remote(self, record: Dict[str, Any]) -> None:
        service = self._service()
        body = {"values": [self._row(record)]}
        request = (
            service.spreadsheets()
            .values()
            .append(
                spreadsheetId=self._sheet_id,
                range="Sheet1!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body=body,
            )
        )
        await _run(request)

    async def _remote_update_row(self, record_id: str, data: Dict[str, Any]) -> None:
        # Locate the row by Record ID (column A) and patch key columns.
        service = self._service()
        result = await _run(
            service.spreadsheets().values().get(
                spreadsheetId=self._sheet_id, range="A:A"
            )
        )
        values = result.get("values", [])
        row_idx = next((i + 1 for i, row in enumerate(values) if row and row[0] == record_id), None)
        if row_idx is None:
            await self._append_remote(data)
            return
        row = self._row(data)
        body = {"values": [row]}
        await _run(
            service.spreadsheets().values().update(
                spreadsheetId=self._sheet_id,
                range=f"A{row_idx}:T{row_idx}",
                valueInputOption="USER_ENTERED",
                body=body,
            )
        )


async def _run(request) -> Any:
    """Execute a sync googleapiclient request off the event loop."""
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, request.execute)


__all__ = ["GoogleSheetsService", "LocalAuditLogger", "SHEET_HEADERS"]