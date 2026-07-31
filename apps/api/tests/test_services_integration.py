from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Barrier

import pytest
from chitaozinho_api.audit import append_audit_event
from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.jobs import (
    get_or_create_job,
    lock_job,
    mark_job_completed,
    mark_job_running,
)
from chitaozinho_api.models import (
    Attestation,
    AuditEvent,
    CaptureSession,
    Job,
    TimestampAttempt,
)
from chitaozinho_api.proof_service import timestamp_capture
from chitaozinho_api.security import ServerSigner
from chitaozinho_api.storage import S3DurableStorage
from chitaozinho_protocol import canonical_bytes, sha256_identifier
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.skipif(
    os.getenv("CHITAOZINHO_RUN_SERVICE_INTEGRATION") != "1",
    reason="local PostgreSQL and Garage integration is opt-in",
)


def test_postgres_and_garage_persist_without_overwrite() -> None:
    settings = Settings()
    assert settings.database_url.startswith("postgresql")
    assert settings.storage_backend == "s3"

    engine = create_database_engine(settings)
    session_id = uuid.uuid4().hex
    now = datetime.now(UTC)
    with Session(engine) as database:
        database.add(
            CaptureSession(
                id=session_id,
                server_challenge="integration-test",
                status="created",
                next_sequence=0,
                created_at=now,
                updated_at=now,
            )
        )
        database.commit()
        assert database.scalar(
            select(CaptureSession).where(CaptureSession.id == session_id)
        )

    storage = S3DurableStorage(settings)
    original = b"garage integration bytes"
    key = storage.put_part(session_id, "integration", 0, original)
    assert storage.read(key) == original
    assert storage.put_part(session_id, "integration", 0, original) == key
    with pytest.raises(FileExistsError):
        storage.put_part(session_id, "integration", 0, b"divergent")
    assert storage.read(key) == original


def test_postgres_serializes_audit_chain_and_job_idempotency() -> None:
    settings = Settings()
    engine = create_database_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    worker_count = 8
    subject_prefix = f"concurrency-{uuid.uuid4().hex}"
    audit_barrier = Barrier(worker_count)

    def append_event(index: int) -> None:
        with factory() as database:
            audit_barrier.wait()
            append_audit_event(
                database,
                "concurrency_test",
                subject_id=f"{subject_prefix}-{index}",
                details={"index": index},
            )
            database.commit()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        list(executor.map(append_event, range(worker_count)))

    with factory() as database:
        events = list(
            database.scalars(select(AuditEvent).order_by(AuditEvent.sequence))
        )
        assert [event.sequence for event in events] == list(range(len(events)))
        previous_hash = None
        for event in events:
            created_at = event.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            created_at = created_at.astimezone(UTC)
            document = {
                "schema_version": "0.1.0",
                "sequence": event.sequence,
                "previous_event_hash": previous_hash,
                "event_type": event.event_type,
                "subject_id": event.subject_id,
                "details": event.details,
                "created_at": created_at.isoformat().replace("+00:00", "Z"),
            }
            assert event.previous_event_hash == previous_hash
            assert event.event_hash == sha256_identifier(canonical_bytes(document))
            previous_hash = event.event_hash
        assert sum(
            event.subject_id is not None
            and event.subject_id.startswith(subject_prefix)
            for event in events
        ) == worker_count

    idempotency_key = f"concurrent-job-{uuid.uuid4().hex}"
    job_barrier = Barrier(worker_count)

    def create_job(_index: int) -> tuple[str, bool]:
        with factory() as database:
            job_barrier.wait()
            job, created = get_or_create_job(
                database,
                kind="concurrency_test",
                idempotency_key=idempotency_key,
                subject_id=subject_prefix,
                payload={"stable": True},
            )
            return job.id, created

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        results = list(executor.map(create_job, range(worker_count)))
    assert len({job_id for job_id, _created in results}) == 1
    assert sum(created for _job_id, created in results) == 1
    with factory() as database:
        assert (
            database.scalar(
                select(func.count(Job.id)).where(
                    Job.idempotency_key == idempotency_key
                )
            )
            == 1
        )

    processing_key = f"concurrent-processing-{uuid.uuid4().hex}"
    processing_barrier = Barrier(2)

    def process_job(_index: int) -> str:
        with factory() as database:
            processing_barrier.wait()
            job, _created = get_or_create_job(
                database,
                kind="concurrency_processing_test",
                idempotency_key=processing_key,
                subject_id=subject_prefix,
                payload={"stable": True},
            )
            job = lock_job(database, job.idempotency_key)
            if job.status == "completed" and job.result is not None:
                return job.result["processor"]
            mark_job_running(database, job, commit=False)
            processor = uuid.uuid4().hex
            mark_job_completed(database, job, {"processor": processor})
            return processor

    with ThreadPoolExecutor(max_workers=2) as executor:
        processors = list(executor.map(process_job, range(2)))
    assert len(set(processors)) == 1
    with factory() as database:
        processed_job = database.scalar(
            select(Job).where(Job.idempotency_key == processing_key)
        )
        assert processed_job is not None
        assert processed_job.status == "completed"
        assert processed_job.attempts == 1


def test_postgres_serializes_attestations_per_session(tmp_path: Path) -> None:
    settings = Settings(
        proofs_path=tmp_path / "proofs",
        server_key_id="server-concurrency",
        server_seed_hex="44" * 32,
    )
    engine = create_database_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    signer = ServerSigner.from_settings(settings)
    assert signer is not None
    session_id = uuid.uuid4().hex
    manifest_hash = "sha256:" + ("55" * 32)
    now = datetime.now(UTC)
    with factory() as database:
        database.add(
            CaptureSession(
                id=session_id,
                server_challenge="concurrency-test",
                status="complete",
                next_sequence=0,
                created_at=now,
                updated_at=now,
                manifest_hash=manifest_hash,
            )
        )
        database.commit()

    barrier = Barrier(2)

    def timestamp(_index: int) -> str:
        with factory() as database:
            capture_session = database.get(CaptureSession, session_id)
            assert capture_session is not None
            barrier.wait()
            return timestamp_capture(
                database,
                settings,
                signer,
                capture_session,
            ).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        attestation_ids = list(executor.map(timestamp, range(2)))
    assert len(set(attestation_ids)) == 2
    with factory() as database:
        attempts = list(
            database.scalars(
                select(TimestampAttempt)
                .where(TimestampAttempt.session_id == session_id)
                .order_by(TimestampAttempt.attempt_number)
            )
        )
        attestations = list(
            database.scalars(
                select(Attestation)
                .where(Attestation.session_id == session_id)
                .order_by(Attestation.sequence)
            )
        )
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]
        assert [attestation.sequence for attestation in attestations] == [0, 1]
        assert (
            attestations[1].previous_attestation_hash
            == attestations[0].document_hash
        )
