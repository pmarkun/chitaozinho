from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Job


def get_or_create_job(
    database: Session,
    *,
    kind: str,
    idempotency_key: str,
    subject_id: str | None,
    payload: dict,
) -> tuple[Job, bool]:
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


def mark_job_running(database: Session, job: Job) -> None:
    now = datetime.now(UTC)
    job.status = "running"
    job.attempts += 1
    job.started_at = now
    job.updated_at = now
    job.last_error = None
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
    job.last_error = f"{type(error).__name__}: {error}"[:2000]
    job.updated_at = datetime.now(UTC)
    database.commit()
