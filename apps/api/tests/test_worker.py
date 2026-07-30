from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.jobs import get_or_create_job
from chitaozinho_api.models import Base, CaptureSession, Job, TimestampAttempt
from chitaozinho_api.security import ServerSigner
from chitaozinho_api.worker import run_once
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


def test_worker_recovers_abandoned_persistent_timestamp_job(
    tmp_path: Path,
) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'worker.db'}",
        proofs_path=tmp_path / "proofs",
        storage_path=tmp_path / "artifacts",
        server_key_id="server-worker",
        server_seed_hex=("33" * 32),
        worker_stale_seconds=1,
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    manifest_hash = "sha256:" + ("42" * 32)
    with factory() as database:
        database.add(
            CaptureSession(
                id="session-worker",
                server_challenge="challenge",
                status="complete",
                next_sequence=0,
                created_at=now,
                updated_at=now,
                manifest_hash=manifest_hash,
            )
        )
        database.commit()
        job, _created = get_or_create_job(
            database,
            kind="rfc3161_timestamp",
            idempotency_key="worker-job",
            subject_id="session-worker",
            payload={"manifest_hash": manifest_hash},
        )
        job.status = "running"
        job.attempts = 1
        job.updated_at = now - timedelta(minutes=5)
        database.commit()

    signer = ServerSigner.from_settings(settings)
    assert signer is not None
    assert run_once(factory, settings, signer)
    with factory() as database:
        job = database.scalar(
            select(Job).where(Job.idempotency_key == "worker-job")
        )
        assert job is not None
        assert job.status == "completed"
        assert job.attempts == 2
        assert job.result is not None
        assert database.scalar(select(func.count(TimestampAttempt.id))) == 1
