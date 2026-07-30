from datetime import UTC, datetime
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.models import Base, CaptureSession, TimestampAttempt
from chitaozinho_api.proof_service import timestamp_capture
from chitaozinho_api.security import ServerSigner
from chitaozinho_protocol import DOMAINS, verify_canonical
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session


def test_tsa_outage_changes_only_timestamp_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'proofs.db'}",
        proofs_path=tmp_path / "proofs",
        server_key_id="server-test",
        server_seed_hex="11" * 32,
        tsa_url="https://tsa.invalid.example",
    )
    signer = ServerSigner.from_settings(settings)
    assert signer is not None

    def unavailable(*_arguments, **_keyword_arguments) -> bytes:
        raise TimeoutError("synthetic TSA outage")

    monkeypatch.setattr(
        "chitaozinho_api.proof_service.request_rfc3161_timestamp",
        unavailable,
    )
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    now = datetime.now(UTC)
    capture = CaptureSession(
        id="tsa-outage-session",
        server_challenge="challenge",
        status="complete",
        next_sequence=0,
        manifest_hash="sha256:" + ("42" * 32),
        created_at=now,
        updated_at=now,
        ended_at=now,
    )
    with Session(engine) as database:
        database.add(capture)
        database.commit()

        attestation = timestamp_capture(database, settings, signer, capture)

        assert capture.status == "complete"
        assert capture.timestamp_status == "failed"
        assert capture.blockchain_status == "not_submitted"
        assert capture.storage_status == "staging"
        assert attestation.document["timestamp_status"] == "failed"
        assert attestation.document["blockchain_status"] == "not_submitted"
        assert verify_canonical(
            DOMAINS["attestation"],
            attestation.document,
            bytes.fromhex(attestation.signature_hex),
            signer.public_key,
        )
        attempt = database.scalar(
            select(TimestampAttempt).where(TimestampAttempt.session_id == capture.id)
        )
        assert attempt is not None
        assert attempt.status == "failed"
        assert attempt.response_path is None
        assert attempt.chain_path is None
        assert attempt.error == "TimeoutError: synthetic TSA outage"
        assert (settings.proofs_path / attempt.query_path).is_file()
