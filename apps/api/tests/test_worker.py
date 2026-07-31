from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.jobs import get_or_create_job, job_retry_delay
from chitaozinho_api.models import Base, CaptureSession, Job, TimestampAttempt
from chitaozinho_api.observability import configure_operational_logging
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


def test_worker_failure_is_structured_without_exception_message(
    caplog,
    tmp_path: Path,
) -> None:
    configure_operational_logging()
    assert logging.getLogger("chitaozinho.worker").level == logging.INFO
    caplog.set_level(logging.INFO, logger="chitaozinho.worker")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'failed-worker.db'}",
        proofs_path=tmp_path / "proofs",
        storage_path=tmp_path / "artifacts",
        server_key_id="server-worker",
        server_seed_hex=("33" * 32),
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as database:
        job, _created = get_or_create_job(
            database,
            kind="rfc3161_timestamp",
            idempotency_key="failed-worker-job",
            subject_id="missing-session",
            payload={"manifest_hash": "token=top-secret"},
        )
        job_id = job.id

    signer = ServerSigner.from_settings(settings)
    assert signer is not None
    assert run_once(factory, settings, signer)

    with factory() as database:
        failed = database.get(Job, job_id)
        assert failed is not None
        assert failed.status == "failed"
        assert failed.last_error == "ValueError"
        assert failed.available_at > failed.updated_at
        assert (
            failed.available_at - failed.updated_at
        ).total_seconds() == settings.worker_retry_base_seconds

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "chitaozinho.worker"
    ]
    assert [record["event"] for record in records] == [
        "job_started",
        "job_failed",
    ]
    assert records[-1]["error_type"] == "ValueError"
    assert "top-secret" not in json.dumps(records)
    assert job_retry_delay(settings, 20) == settings.worker_retry_max_seconds
