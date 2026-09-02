from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .audit import append_audit_event
from .config import Settings
from .database import create_database_engine
from .models import CaptureSession
from .observability import configure_operational_logging
from .storage import DurableStorage, create_storage


def expire_due_sessions(
    factory: sessionmaker[Session],
    storage: DurableStorage,
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    current = now or datetime.now(UTC)
    expired = 0
    failed = 0
    with factory() as database:
        sessions = list(
            database.scalars(
                select(CaptureSession)
                .where(
                    CaptureSession.storage_expires_at.is_not(None),
                    CaptureSession.storage_expires_at <= current,
                    CaptureSession.storage_expired_at.is_(None),
                )
                .order_by(CaptureSession.storage_expires_at, CaptureSession.id)
            )
        )
        for capture_session in sessions:
            try:
                storage.delete_session(capture_session.id)
                capture_session.storage_status = "expired"
                capture_session.storage_expired_at = current
                append_audit_event(
                    database,
                    "evidence_storage_expired",
                    subject_id=capture_session.id,
                    details={"expired_at": current.isoformat()},
                )
                database.commit()
                expired += 1
            except Exception as error:
                database.rollback()
                current_session = database.get(CaptureSession, capture_session.id)
                if current_session is not None:
                    current_session.storage_status = "expiration_failed"
                    append_audit_event(
                        database,
                        "evidence_storage_expiration_failed",
                        subject_id=current_session.id,
                        details={"error_type": type(error).__name__},
                    )
                    database.commit()
                failed += 1
    return expired, failed


def main() -> None:
    configure_operational_logging()
    settings = Settings()
    if settings.env != "beta":
        raise RuntimeError("retention cleanup is only enabled in beta")
    engine = create_database_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    expired, failed = expire_due_sessions(factory, create_storage(settings))
    print(f"retention_cleanup expired={expired} failed={failed}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
