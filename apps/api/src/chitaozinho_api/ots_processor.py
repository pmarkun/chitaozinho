from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import exists, select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings
from .database import create_database_engine
from .jobs import (
    get_or_create_job,
    job_retry_delay,
    mark_job_completed,
    mark_job_failed,
    mark_job_running,
)
from .models import CaptureSession, Job, MerkleBatch, MerkleMembership
from .observability import configure_operational_logging, emit_worker_log
from .proof_service import (
    OtsPendingConfirmation,
    create_merkle_batch,
    upgrade_merkle_batch,
)
from .proof_storage import ProofStorage, create_proof_storage
from .security import ServerSigner


def create_pending_batch(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    proof_storage: ProofStorage,
) -> MerkleBatch | None:
    membership_exists = exists(
        select(MerkleMembership.id).where(
            MerkleMembership.session_id == CaptureSession.id
        )
    )
    statement = (
        select(CaptureSession.id)
        .where(
            CaptureSession.manifest_hash.is_not(None),
            CaptureSession.blockchain_status == "not_submitted",
            CaptureSession.storage_status.not_in(["expired", "expiration_failed"]),
            ~membership_exists,
        )
        .order_by(CaptureSession.ended_at, CaptureSession.id)
        .limit(settings.ots_batch_size)
    )
    if database.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    session_ids = list(database.scalars(statement))
    if not session_ids:
        return None
    batch = create_merkle_batch(
        database,
        settings,
        signer,
        session_ids,
        submit_ots=True,
        proof_storage=proof_storage,
    )
    get_or_create_job(
        database,
        kind="ots_upgrade",
        idempotency_key=f"ots-upgrade:{batch.id}",
        subject_id=batch.id,
        payload={"batch_id": batch.id},
    )
    return batch


def ensure_upgrade_jobs(database: Session) -> None:
    batches = list(
        database.scalars(
            select(MerkleBatch)
            .where(MerkleBatch.status == "pending_confirmation")
            .order_by(MerkleBatch.created_at)
        )
    )
    for batch in batches:
        get_or_create_job(
            database,
            kind="ots_upgrade",
            idempotency_key=f"ots-upgrade:{batch.id}",
            subject_id=batch.id,
            payload={"batch_id": batch.id},
        )


def claim_upgrade_job(database: Session) -> Job | None:
    statement = (
        select(Job)
        .where(
            Job.kind == "ots_upgrade",
            Job.status.in_(["pending", "failed"]),
            Job.available_at <= datetime.now(UTC),
        )
        .order_by(Job.available_at, Job.created_at)
        .limit(1)
    )
    if database.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    return database.scalar(statement)


def reschedule_pending(database: Session, job: Job, settings: Settings) -> None:
    now = datetime.now(UTC)
    job.status = "pending"
    job.available_at = now + timedelta(seconds=settings.ots_upgrade_retry_seconds)
    job.updated_at = now
    job.last_error = None
    database.commit()


def process_upgrade_job(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    proof_storage: ProofStorage,
    job: Job,
) -> None:
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
        batch = database.get(MerkleBatch, job.subject_id)
        if batch is None:
            raise ValueError("OpenTimestamps job references a missing batch")
        complement = upgrade_merkle_batch(
            database,
            settings,
            signer,
            batch,
            proof_storage=proof_storage,
        )
        if complement.status == "pending_confirmation":
            reschedule_pending(database, job, settings)
        else:
            mark_job_completed(
                database,
                job,
                {
                    "batch_id": batch.id,
                    "complement_id": complement.id,
                    "status": complement.status,
                },
            )
    except OtsPendingConfirmation:
        database.rollback()
        current = database.get(Job, job.id)
        if current is not None:
            reschedule_pending(database, current, settings)
    except Exception as error:
        database.rollback()
        current = database.get(Job, job.id)
        if current is not None:
            mark_job_failed(
                database,
                current,
                error,
                retry_delay_seconds=job_retry_delay(settings, current.attempts),
            )
        raise


def run_once(
    factory: sessionmaker[Session],
    settings: Settings,
    signer: ServerSigner,
    proof_storage: ProofStorage,
) -> tuple[int, int]:
    batches_created = 0
    upgrades_processed = 0
    with factory() as database:
        ensure_upgrade_jobs(database)
        if create_pending_batch(database, settings, signer, proof_storage) is not None:
            batches_created = 1
    for _index in range(10):
        with factory() as database:
            job = claim_upgrade_job(database)
            if job is None:
                break
            process_upgrade_job(database, settings, signer, proof_storage, job)
            upgrades_processed += 1
    return batches_created, upgrades_processed


def main() -> None:
    configure_operational_logging()
    settings = Settings()
    if not settings.ots_enabled:
        print("opentimestamps disabled")
        return
    signer = ServerSigner.from_settings(settings)
    if signer is None:
        raise RuntimeError("server signing key is not configured")
    engine = create_database_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    proof_storage = create_proof_storage(settings)
    batches, upgrades = run_once(factory, settings, signer, proof_storage)
    print(f"opentimestamps batches_created={batches} upgrades_processed={upgrades}")


if __name__ == "__main__":
    main()
