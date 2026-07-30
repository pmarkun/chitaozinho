from __future__ import annotations

from datetime import UTC, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from .audit import append_audit_event
from .config import Settings
from .models import CaptureSession
from .storage import DurableStorage


def protect_final_artifact(
    database: Session,
    settings: Settings,
    storage: DurableStorage,
    capture_session: CaptureSession,
    *,
    name: str,
    path: Path,
    digest: str,
) -> str:
    retention_start = capture_session.ended_at or capture_session.updated_at
    if retention_start.tzinfo is None:
        retention_start = retention_start.replace(tzinfo=UTC)
    retain_until = retention_start.astimezone(UTC) + timedelta(
        days=settings.retention_days
    )
    try:
        result = storage.protect_final(
            capture_session.id,
            name,
            path,
            digest,
            retain_until,
        )
        status = result.status
        details = {
            "artifact_name": name,
            "artifact_hash": digest,
            "storage_key": result.key,
            "storage_status": result.status,
            "version_id": result.version_id,
            "retain_until": (
                result.retain_until.isoformat() if result.retain_until is not None else None
            ),
        }
    except Exception as error:
        status = "retention_failed"
        details = {
            "artifact_name": name,
            "artifact_hash": digest,
            "storage_status": status,
            "error_type": type(error).__name__,
        }
    capture_session.storage_status = status
    append_audit_event(
        database,
        "evidence_retention_evaluated",
        subject_id=capture_session.id,
        details=details,
    )
    database.commit()
    return status
