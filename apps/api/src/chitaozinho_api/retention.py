from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chitaozinho_protocol import sha256_identifier
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
    retain_until = retention_deadline(
        capture_session,
        settings.retention_days,
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
        if (
            settings.env == "beta"
            and result.status == "stored"
            and (
                capture_session.storage_expires_at is None
                or capture_session.storage_expires_at < retain_until
            )
        ):
            capture_session.storage_expires_at = retain_until
        details = {
            "artifact_name": name,
            "artifact_hash": digest,
            "storage_key_hash": sha256_identifier(result.key.encode()),
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


def retention_deadline(
    capture_session: CaptureSession,
    retention_days: int,
    *,
    protected_at: datetime | None = None,
) -> datetime:
    capture_end = capture_session.ended_at or capture_session.updated_at
    if capture_end.tzinfo is None:
        capture_end = capture_end.replace(tzinfo=UTC)
    capture_end = capture_end.astimezone(UTC)
    protected_at = protected_at or datetime.now(UTC)
    if protected_at.tzinfo is None:
        protected_at = protected_at.replace(tzinfo=UTC)
    protected_at = protected_at.astimezone(UTC)
    return max(capture_end, protected_at) + timedelta(days=retention_days)
