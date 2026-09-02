from __future__ import annotations

from datetime import UTC, datetime, timedelta

from chitaozinho_api.models import AuditEvent, Base, CaptureSession
from chitaozinho_api.retention_cleanup import expire_due_sessions
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker


class CleanupStorage:
    persistence_state = "stored"

    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.deleted: list[str] = []

    def delete_session(self, session_id: str) -> None:
        if self.failures:
            self.failures -= 1
            raise RuntimeError("synthetic deletion failure")
        self.deleted.append(session_id)


def test_expiration_is_verified_audited_and_idempotent(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with Session(engine) as database:
        database.add(
            CaptureSession(
                id="due-session",
                server_challenge="challenge",
                status="complete",
                next_sequence=0,
                created_at=now - timedelta(days=40),
                updated_at=now - timedelta(days=40),
                ended_at=now - timedelta(days=40),
                storage_status="stored",
                storage_expires_at=now - timedelta(days=1),
            )
        )
        database.commit()

    storage = CleanupStorage()
    assert expire_due_sessions(factory, storage, now=now) == (1, 0)
    assert expire_due_sessions(factory, storage, now=now) == (0, 0)
    assert storage.deleted == ["due-session"]
    with Session(engine) as database:
        capture = database.get(CaptureSession, "due-session")
        assert capture is not None
        assert capture.storage_status == "expired"
        assert capture.storage_expired_at is not None
        event = database.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "evidence_storage_expired")
        )
        assert event is not None


def test_expiration_failure_is_retried(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'cleanup-retry.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with Session(engine) as database:
        database.add(
            CaptureSession(
                id="retry-session",
                server_challenge="challenge",
                status="complete",
                next_sequence=0,
                created_at=now,
                updated_at=now,
                ended_at=now,
                storage_status="stored",
                storage_expires_at=now - timedelta(seconds=1),
            )
        )
        database.commit()

    storage = CleanupStorage(failures=1)
    assert expire_due_sessions(factory, storage, now=now) == (0, 1)
    assert expire_due_sessions(factory, storage, now=now) == (1, 0)
    with Session(engine) as database:
        capture = database.get(CaptureSession, "retry-session")
        assert capture is not None
        assert capture.storage_status == "expired"
        events = list(
            database.scalars(
                select(AuditEvent)
                .where(AuditEvent.subject_id == "retry-session")
                .order_by(AuditEvent.sequence)
            )
        )
        assert [event.event_type for event in events] == [
            "evidence_storage_expiration_failed",
            "evidence_storage_expired",
        ]
