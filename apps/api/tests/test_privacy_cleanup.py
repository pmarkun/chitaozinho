from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from chitaozinho_api.audit import append_audit_event, verify_audit_chain
from chitaozinho_api.models import (
    AuditCheckpoint,
    AuditEvent,
    CaptureSession,
    MerkleBatch,
    MerkleMembership,
    User,
)
from chitaozinho_api.privacy_cleanup import cleanup_personal_data, twelve_months_ago
from chitaozinho_api.proof_storage import LocalProofStorage
from sqlalchemy import create_engine, delete, func, select, update
from sqlalchemy.exc import DatabaseError
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def environment(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'privacy.db'}"
    monkeypatch.setenv("CHITAOZINHO_DATABASE_URL", url)
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(url)
    yield sessionmaker(engine, expire_on_commit=False), LocalProofStorage(tmp_path / "proofs")
    engine.dispose()


def capture(identifier, when, owner=None):
    return CaptureSession(
        id=identifier,
        owner_user_id=owner,
        server_challenge="challenge",
        evidence_mode="hash_only",
        storage_status="hash_only",
        status="complete",
        next_sequence=0,
        created_at=when,
        updated_at=when,
        ended_at=when,
    )


def audit_at(database, when):
    with patch("chitaozinho_api.audit.datetime") as clock:
        clock.now.return_value = when
        append_audit_event(
            database, "security", subject_id="private-subject", details={"test": True}
        )


def exercise_checkpoint(factory, proofs):
    now = datetime.now(UTC)
    with factory.begin() as database:
        audit_at(database, now - timedelta(days=31))
        audit_at(database, now)
    with factory.begin() as database, pytest.raises(DatabaseError), database.begin_nested():
        database.execute(delete(AuditEvent).where(AuditEvent.sequence == 0))
    dry = cleanup_personal_data(factory, proofs, now=now)
    assert dry["security_records"] == 1
    with factory() as database:
        assert database.get(AuditCheckpoint, 1) is None
        assert verify_audit_chain(database) == 2
    result = cleanup_personal_data(factory, proofs, now=now, apply=True)
    assert result["security_records"] == 1
    with factory.begin() as database:
        assert database.get(AuditCheckpoint, 1).sequence == 0
        assert verify_audit_chain(database) == 2  # recent + cleanup summary
        assert database.scalar(select(func.min(AuditEvent.sequence))) == 1
        with pytest.raises(DatabaseError), database.begin_nested():
            database.execute(delete(AuditEvent).where(AuditEvent.sequence == 1))
        with pytest.raises(DatabaseError), database.begin_nested():
            database.execute(update(AuditEvent).values(details={"tamper": True}))
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["security_records"] == 0


def test_checkpointed_retirement_preserves_chain_and_db_protection(environment):
    exercise_checkpoint(*environment)


def test_empty_retained_chain_continues_sequence(environment):
    factory, proofs = environment
    now = datetime.now(UTC)
    with factory.begin() as database:
        audit_at(database, now - timedelta(days=31))
    cleanup_personal_data(factory, proofs, now=now, apply=True)
    with factory() as database:
        assert verify_audit_chain(database) == 1
        assert database.scalar(select(AuditEvent.sequence)) == 1


def test_calendar_year_and_leap_day():
    assert twelve_months_ago(datetime(2024, 2, 29, tzinfo=UTC)) == datetime(2023, 2, 28, tzinfo=UTC)


def test_shared_batch_survives_until_last_session_and_dry_run_is_read_only(environment):
    factory, proofs = environment
    now = datetime.now(UTC)
    with factory.begin() as database:
        database.add_all([capture("old", now - timedelta(days=370)), capture("recent", now)])
        database.add(
            MerkleBatch(
                id="batch",
                root_hash="sha256:" + "a" * 64,
                status="confirmed",
                root_path="merkle/batch/root.bin",
                created_at=now,
            )
        )
        database.flush()
        for identifier in ["old", "recent"]:
            database.add(
                MerkleMembership(
                    batch_id="batch",
                    session_id=identifier,
                    proof_path=f"sessions/{identifier}/proof.json",
                    proof={},
                )
            )
            proofs.put_once(f"sessions/{identifier}/proof.json", b"proof")
        proofs.put_once("merkle/batch/root.bin", b"root")
    assert cleanup_personal_data(factory, proofs, now=now)["sessions"] == 1
    assert proofs.read("sessions/old/proof.json") == b"proof"
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["sessions"] == 1
    assert proofs.read("merkle/batch/root.bin") == b"root"
    with factory() as database:
        assert database.get(CaptureSession, "old") is None
        assert database.get(CaptureSession, "recent") is not None
        assert database.get(MerkleBatch, "batch") is not None
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["sessions"] == 0
    with factory.begin() as database:
        database.get(CaptureSession, "recent").created_at = now - timedelta(days=370)
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["sessions"] == 1
    assert not (proofs.root / "merkle/batch").exists()


def test_partial_proof_deletion_retries_without_losing_metadata(environment):
    factory, proofs = environment
    now = datetime.now(UTC)
    with factory.begin() as database:
        database.add(capture("retry", now - timedelta(days=370)))
    with patch.object(proofs, "delete_scope", side_effect=RuntimeError("synthetic failure")):
        assert cleanup_personal_data(factory, proofs, now=now, apply=True)["failures"] == 1
    with factory() as database:
        assert database.get(CaptureSession, "retry") is not None
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["sessions"] == 1


def test_account_erasure_is_scoped_and_legacy_retention_is_not_bypassed(environment):
    factory, proofs = environment
    now = datetime.now(UTC)
    with factory.begin() as database:
        database.add_all(
            [
                User(id="one", email="one@example.test", created_at=now),
                User(id="two", email="two@example.test", created_at=now),
            ]
        )
        database.add_all([capture("a", now, "one"), capture("b", now, "two")])
        legacy = capture("legacy", now - timedelta(days=370))
        legacy.evidence_mode = "remote"
        database.add(legacy)
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["failures"] == 1
    assert cleanup_personal_data(factory, proofs, user_id="one", apply=True)["accounts"] == 1
    with factory() as database:
        assert database.get(User, "one") is None
        assert database.get(CaptureSession, "a") is None
        assert database.get(User, "two") is not None
        assert database.get(CaptureSession, "b") is not None
        assert database.get(CaptureSession, "legacy") is not None


@pytest.mark.skipif(
    os.getenv("CHITAOZINHO_RUN_SERVICE_INTEGRATION") != "1",
    reason="isolated PostgreSQL integration only",
)
def test_postgres_checkpoint_and_protection(tmp_path, monkeypatch):
    import uuid

    from sqlalchemy import text
    from sqlalchemy.engine import make_url

    # Isolate the complete migration/retirement in a unique schema, even when
    # other integration tests have created a synthetic audit chain.
    engine = create_engine(os.environ["CHITAOZINHO_DATABASE_URL"])
    schema = "privacy_test_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = make_url(os.environ["CHITAOZINHO_DATABASE_URL"]).update_query_dict(
        {"options": f"-csearch_path={schema}"}
    )
    isolated = create_engine(url)
    try:
        monkeypatch.setenv("CHITAOZINHO_DATABASE_URL", url.render_as_string(hide_password=False))
        command.upgrade(Config("alembic.ini"), "head")
        exercise_checkpoint(
            sessionmaker(isolated, expire_on_commit=False),
            LocalProofStorage(tmp_path / "pg-proofs"),
        )
    finally:
        isolated.dispose()
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


def test_proof_deletion_is_scoped_and_fails_on_partial_s3_errors():
    from chitaozinho_api.proof_storage import S3ProofStorage

    class Client:
        def __init__(self):
            self.keys = ["proofs/sessions/one/a", "proofs/sessions/two/b"]
            self.partial = True

        def list_objects_v2(self, *, Bucket, Prefix):
            return {"Contents": [{"Key": key} for key in self.keys if key.startswith(Prefix)]}

        def delete_objects(self, *, Bucket, Delete):
            if self.partial:
                return {"Errors": [{"Code": "AccessDenied"}]}
            for item in Delete["Objects"]:
                self.keys.remove(item["Key"])
            return {}

    storage = object.__new__(S3ProofStorage)
    storage.bucket = "synthetic"
    storage.client = Client()
    with pytest.raises(RuntimeError, match="partial"):
        storage.delete_scope("sessions", "one")
    storage.client.partial = False
    storage.delete_scope("sessions", "one")
    storage.delete_scope("sessions", "one")
    assert storage.client.keys == ["proofs/sessions/two/b"]
    with pytest.raises(ValueError):
        storage.delete_scope("sessions", "../two")


def test_running_jobs_prevent_capture_and_proof_deletion(environment):
    from chitaozinho_api.jobs import get_or_create_job, mark_job_running

    factory, proofs = environment
    now = datetime.now(UTC)
    with factory() as database:
        database.add(capture("busy", now - timedelta(days=370)))
        job = get_or_create_job(
            database, kind="package", idempotency_key="busy", subject_id="busy", payload={}
        )
        mark_job_running(database, job)
    assert cleanup_personal_data(factory, proofs, now=now, apply=True)["failures"] == 1
    with factory() as database:
        assert database.get(CaptureSession, "busy") is not None
