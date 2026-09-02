from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from chitaozinho_api.config import Settings
from chitaozinho_api.database import create_database_engine
from chitaozinho_api.models import (
    Base,
    CaptureSession,
    Job,
    MerkleBatch,
    MerkleMembership,
    OtsComplement,
)
from chitaozinho_api.ots_processor import run_once
from chitaozinho_api.proof_storage import LocalProofStorage
from chitaozinho_api.security import ServerSigner
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker


def test_processor_batches_pending_sessions_and_upgrades_without_bitcoin_node(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'ots.db'}",
        proofs_path=tmp_path / "proofs",
        storage_path=tmp_path / "artifacts",
        server_key_id="server-ots",
        server_seed_hex=("44" * 32),
        ots_enabled=True,
        ots_upgrade_retry_seconds=300,
    )
    engine = create_database_engine(settings)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with factory() as database:
        database.add_all(
            [
                CaptureSession(
                    id=f"session-{index}",
                    server_challenge="challenge",
                    status="complete",
                    next_sequence=0,
                    created_at=now,
                    updated_at=now,
                    ended_at=now,
                    manifest_hash=f"sha256:{index:064x}",
                    timestamp_status="not_requested",
                    blockchain_status="not_submitted",
                    storage_status="stored",
                )
                for index in (1, 2)
            ]
        )
        database.commit()

    def fake_stamp(root_hash, root_file, proof_file, calendars):
        assert len(calendars) == 4
        root_file.write_bytes(bytes.fromhex(root_hash.removeprefix("sha256:")))
        proof_file.write_bytes(b"pending-ots-proof")

    upgrade_ready = False

    def fake_upgrade(original, complement):
        complement.write_bytes(
            original.read_bytes() + (b"-bitcoin" if upgrade_ready else b"")
        )
        return upgrade_ready

    monkeypatch.setattr("chitaozinho_api.proof_service.stamp_ots", fake_stamp)
    monkeypatch.setattr("chitaozinho_api.proof_service.upgrade_ots", fake_upgrade)
    monkeypatch.setattr(
        "chitaozinho_api.proof_service.inspect_ots",
        lambda _proof: "bitcoin_attestation_available",
    )
    signer = ServerSigner.from_settings(settings)
    assert signer is not None
    proof_storage = LocalProofStorage(settings.proofs_path)

    assert run_once(factory, settings, signer, proof_storage) == (1, 1)
    with factory() as database:
        batch = database.scalar(select(MerkleBatch))
        assert batch is not None
        assert batch.status == "pending_confirmation"
        assert database.scalar(select(func.count(MerkleMembership.id))) == 2
        job = database.scalar(select(Job).where(Job.kind == "ots_upgrade"))
        assert job is not None
        assert job.status == "pending"
        job.available_at = datetime.now(UTC)
        database.commit()
        assert proof_storage.read(batch.ots_proof_path or "") == b"pending-ots-proof"

    upgrade_ready = True
    assert run_once(factory, settings, signer, proof_storage) == (0, 1)
    with factory() as database:
        batch = database.scalar(select(MerkleBatch))
        assert batch is not None
        assert batch.status == "bitcoin_attestation_available"
        assert database.scalar(select(func.count(OtsComplement.id))) == 1
        job = database.scalar(select(Job).where(Job.kind == "ots_upgrade"))
        assert job is not None
        assert job.status == "completed"
        sessions = list(database.scalars(select(CaptureSession)))
        assert {value.blockchain_status for value in sessions} == {
            "bitcoin_attestation_available"
        }
