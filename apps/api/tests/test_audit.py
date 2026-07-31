from __future__ import annotations

from pathlib import Path

import pytest
from chitaozinho_api.audit import append_audit_event, verify_audit_chain
from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.models import AuditEvent, Base
from sqlalchemy import update
from sqlalchemy.orm import Session


def test_audit_chain_verification_detects_persisted_tampering(
    tmp_path: Path,
) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'audit.db'}")
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    with Session(engine) as database:
        append_audit_event(
            database,
            "first",
            subject_id="subject",
            details={"value": 1},
        )
        append_audit_event(
            database,
            "second",
            subject_id="subject",
            details={"value": 2},
        )
        database.commit()
        assert verify_audit_chain(database) == 2

    with engine.begin() as connection:
        connection.execute(
            update(AuditEvent)
            .where(AuditEvent.sequence == 0)
            .values(details={"value": "tampered"})
        )

    with (
        Session(engine) as database,
        pytest.raises(ValueError, match="hash mismatch at 0"),
    ):
        verify_audit_chain(database)
