from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import Job


def advisory_lock_id(idempotency_key: str) -> int:
    digest = hashlib.sha256(idempotency_key.encode()).digest()
    return int.from_bytes(digest[:8], signed=True)


def acquire_job_advisory_lock(
    database: Session,
    idempotency_key: str,
) -> None:
    if database.get_bind().dialect.name == "postgresql":
        database.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": advisory_lock_id(idempotency_key)},
        )


def get_or_create_job(
    database: Session,
    *,
    kind: str,
    idempotency_key: str,
    subject_id: str | None,
    payload: dict,
) -> tuple[Job, bool]:
    acquire_job_advisory_lock(database, idempotency_key)
    existing = database.scalar(
        select(Job).where(Job.idempotency_key == idempotency_key)
    )
    if existing is not None:
        if (
            existing.kind != kind
            or existing.subject_id != subject_id
            or existing.payload != payload
        ):
            raise ValueError("job idempotency key reused with divergent input")
        return existing, False
    now = datetime.now(UTC)
    job = Job(
        id=uuid.uuid4().hex,
        kind=kind,
        idempotency_key=idempotency_key,
        subject_id=subject_id,
        payload=payload,
        status="pending",
        attempts=0,
        available_at=now,
        created_at=now,
        updated_at=now,
    )
    database.add(job)
    database.commit()
    return job, True


def lock_job(database: Session, idempotency_key: str) -> Job:
    acquire_job_advisory_lock(database, idempotency_key)
    statement = select(Job).where(Job.idempotency_key == idempotency_key)
    if database.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update()
    job = database.scalar(statement.execution_options(populate_existing=True))
    if job is None:
        raise ValueError("job no longer exists")
    return job


def mark_job_running(database: Session, job: Job, *, commit: bool = True) -> None:
    now = datetime.now(UTC)
    job.status = "running"
    job.attempts += 1
    job.started_at = now
    job.updated_at = now
    job.last_error = None
    if commit:
        database.commit()


def mark_job_completed(database: Session, job: Job, result: dict) -> None:
    now = datetime.now(UTC)
    job.status = "completed"
    job.result = result
    job.completed_at = now
    job.updated_at = now
    database.commit()


def mark_job_failed(database: Session, job: Job, error: Exception) -> None:
    job.status = "failed"
    job.last_error = type(error).__name__
    job.updated_at = datetime.now(UTC)
    database.commit()
