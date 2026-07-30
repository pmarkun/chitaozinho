from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DatabaseError


def test_migrations_match_models_and_protect_audit_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "migrations.db"
    database_url = f"sqlite:///{database_path}"
    monkeypatch.setenv("CHITAOZINHO_DATABASE_URL", database_url)
    configuration = Config("alembic.ini")
    command.upgrade(configuration, "head")
    command.check(configuration)

    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO audit_events (
                    sequence, previous_event_hash, event_type, subject_id,
                    details, event_hash, created_at
                ) VALUES (
                    0, NULL, 'migration_test', NULL,
                    '{}', :event_hash, CURRENT_TIMESTAMP
                )
                """
            ),
            {"event_hash": "sha256:" + ("0" * 64)},
        )
    with pytest.raises(DatabaseError, match="append-only"), engine.begin() as connection:
        connection.execute(
            text("UPDATE audit_events SET event_type = 'tampered' WHERE sequence = 0")
        )
    with pytest.raises(DatabaseError, match="append-only"), engine.begin() as connection:
        connection.execute(text("DELETE FROM audit_events WHERE sequence = 0"))
