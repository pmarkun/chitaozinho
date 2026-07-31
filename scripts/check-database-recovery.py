from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime

from chitaozinho_api.audit import append_audit_event, verify_audit_chain
from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.jobs import get_or_create_job
from chitaozinho_api.models import CaptureSession, Job
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def seed_synthetic(database: Session, marker: str) -> None:
    now = datetime.now(UTC)
    database.add(
        CaptureSession(
            id=marker,
            server_challenge="synthetic-backup-smoke",
            status="created",
            next_sequence=0,
            created_at=now,
            updated_at=now,
        )
    )
    append_audit_event(
        database,
        "synthetic_backup_smoke_created",
        subject_id=marker,
        details={"synthetic": True},
    )
    database.commit()
    get_or_create_job(
        database,
        kind="synthetic_backup_smoke",
        idempotency_key=f"backup:{marker}",
        subject_id=marker,
        payload={"synthetic": True},
    )


def validate(database: Session) -> dict[str, int]:
    session_count = database.scalar(select(func.count(CaptureSession.id))) or 0
    job_count = database.scalar(select(func.count(Job.id))) or 0
    audit_count = verify_audit_chain(database)
    return {
        "audit_events": audit_count,
        "capture_sessions": session_count,
        "jobs": job_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-synthetic")
    args = parser.parse_args()
    engine = create_database_engine(Settings())
    with Session(engine) as database:
        if args.seed_synthetic:
            seed_synthetic(database, args.seed_synthetic)
        result = validate(database)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
