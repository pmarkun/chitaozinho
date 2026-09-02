from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import create_database_engine
from .jobs import (
    job_retry_delay,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)
from .models import CaptureSession, Job
from .observability import configure_operational_logging, emit_worker_log
from .proof_service import timestamp_capture
from .proof_storage import ProofStorage, create_proof_storage
from .security import ServerSigner


def claim_job(database: Session, settings: Settings) -> Job | None:
    stale_before = datetime.now(UTC) - timedelta(
        seconds=settings.worker_stale_seconds
    )
    statement = (
        select(Job)
        .where(
            Job.kind == "rfc3161_timestamp",
            or_(
                Job.status.in_(["pending", "failed"]),
                (Job.status == "running") & (Job.updated_at < stale_before),
            ),
            Job.available_at <= datetime.now(UTC),
        )
        .order_by(Job.created_at)
        .limit(1)
    )
    if database.bind is not None and database.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    return database.scalar(statement)


def run_once(
    factory: sessionmaker[Session],
    settings: Settings,
    signer: ServerSigner,
    proof_storage: ProofStorage | None = None,
) -> bool:
    proof_storage = proof_storage or create_proof_storage(settings)
    with factory() as database:
        job = claim_job(database, settings)
        if job is None:
            return False
        mark_job_running(database, job)
        emit_worker_log(
            event="job_started",
            job_id=job.id,
            job_kind=job.kind,
            status=job.status,
            attempts=job.attempts,
            subject_id=job.subject_id,
        )
        try:
            capture_session = database.get(CaptureSession, job.subject_id)
            if capture_session is None or capture_session.manifest_hash is None:
                raise ValueError("timestamp job references an unfinished session")
            if job.payload.get("manifest_hash") != capture_session.manifest_hash:
                raise ValueError("timestamp job manifest hash is stale")
            attestation = timestamp_capture(
                database,
                settings,
                signer,
                capture_session,
                proof_storage=proof_storage,
            )
            mark_job_completed(
                database,
                job,
                {"attestation_id": attestation.id},
            )
            emit_worker_log(
                event="job_completed",
                job_id=job.id,
                job_kind=job.kind,
                status=job.status,
                attempts=job.attempts,
                subject_id=job.subject_id,
            )
        except Exception as error:
            database.rollback()
            current = database.get(Job, job.id)
            if current is not None:
                mark_job_failed(
                    database,
                    current,
                    error,
                    retry_delay_seconds=job_retry_delay(
                        settings,
                        current.attempts,
                    ),
                )
                emit_worker_log(
                    event="job_failed",
                    job_id=current.id,
                    job_kind=current.kind,
                    status=current.status,
                    attempts=current.attempts,
                    subject_id=current.subject_id,
                    error_type=type(error).__name__,
                )
        return True


def main() -> None:
    configure_operational_logging()
    settings = Settings()
    signer = ServerSigner.from_settings(settings)
    if signer is None:
        raise RuntimeError("server signing key is not configured")
    engine = create_database_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    proof_storage = create_proof_storage(settings)
    while True:
        worked = run_once(factory, settings, signer, proof_storage)
        if not worked:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
