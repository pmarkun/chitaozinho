from __future__ import annotations

from datetime import UTC, datetime

from chitaozinho_protocol import canonical_bytes, sha256_identifier
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from .models import AuditEvent

AUDIT_ADVISORY_LOCK_ID = 1_128_815_444


def append_audit_event(
    database: Session,
    event_type: str,
    *,
    subject_id: str | None,
    details: dict,
) -> AuditEvent:
    bind = database.get_bind()
    if bind.dialect.name == "postgresql":
        database.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": AUDIT_ADVISORY_LOCK_ID},
        )
    previous = database.scalar(
        select(AuditEvent).order_by(AuditEvent.sequence.desc())
    )
    sequence = 0 if previous is None else previous.sequence + 1
    created_at = datetime.now(UTC)
    document = {
        "schema_version": "0.1.0",
        "sequence": sequence,
        "previous_event_hash": None if previous is None else previous.event_hash,
        "event_type": event_type,
        "subject_id": subject_id,
        "details": details,
        "created_at": created_at.isoformat().replace("+00:00", "Z"),
    }
    audit_event = AuditEvent(
        sequence=sequence,
        previous_event_hash=document["previous_event_hash"],
        event_type=event_type,
        subject_id=subject_id,
        details=details,
        event_hash=sha256_identifier(canonical_bytes(document)),
        created_at=created_at,
    )
    database.add(audit_event)
    return audit_event
