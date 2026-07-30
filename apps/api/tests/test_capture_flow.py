from __future__ import annotations

import json
import subprocess
from datetime import UTC
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import create_app
from chitaozinho_api.models import AuditEvent, Incident, Job, TimestampAttempt
from chitaozinho_protocol import (
    DOMAINS,
    base64url_encode,
    canonical_bytes,
    sha256_identifier,
    sign_canonical,
    verify_canonical,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import select

SERVER_SEED = bytes([11]) * 32
CLIENT_SEED = bytes([12]) * 32
SCHEMA_DIR = Path(__file__).parents[3] / "packages" / "schemas"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        storage_path=tmp_path / "artifacts",
        proofs_path=tmp_path / "proofs",
        server_key_id="server-test",
        server_seed_hex=SERVER_SEED.hex(),
    )
    return TestClient(create_app(settings, create_tables=True))


def public_key(seed: bytes) -> bytes:
    return (
        Ed25519PrivateKey.from_private_bytes(seed)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


def signed_entry(entry: dict) -> dict:
    return {
        "entry": entry,
        "entry_hash": sha256_identifier(canonical_bytes(entry)),
        "signature_hex": sign_canonical(DOMAINS["entry"], entry, CLIENT_SEED).hex(),
    }


def test_session_event_part_finalize_and_idempotency(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = client.post("/v1/sessions")
    assert created.status_code == 201
    session = created.json()
    session_id = session["session_id"]

    registered = client.post(
        f"/v1/sessions/{session_id}/keys",
        json={
            "key_id": "client-test",
            "public_key": base64url_encode(public_key(CLIENT_SEED)),
        },
    )
    assert registered.status_code == 204

    invalid_genesis = {
        "protocol_version": "0.1.0",
        "entry_type": "marker",
        "session_id": session_id,
        "sequence": 0,
        "previous_entry_hash": None,
        "client_clock_id": "clock-1",
        "client_monotonic_time": 0,
        "client_wall_time": "2026-07-30T15:00:00-03:00",
        "server_challenge": session["server_challenge"],
    }
    rejected_genesis = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "invalid-genesis"},
        json=signed_entry(invalid_genesis),
    )
    assert rejected_genesis.status_code == 422

    start_entry = {
        "protocol_version": "0.1.0",
        "entry_type": "capture_started",
        "session_id": session_id,
        "sequence": 0,
        "previous_entry_hash": None,
        "client_clock_id": "clock-1",
        "client_monotonic_time": 0,
        "client_wall_time": "2026-07-30T15:00:00-03:00",
        "server_challenge": session["server_challenge"],
    }
    start_body = signed_entry(start_entry)
    recorded = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "start-1"},
        json=start_body,
    )
    assert recorded.status_code == 201
    assert recorded.json()["status"] == "recorded"

    replayed = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "start-1"},
        json=start_body,
    )
    assert replayed.status_code == 200
    assert replayed.json()["status"] == "already_recorded"

    invalid_clock_change = {
        "protocol_version": "0.1.0",
        "entry_type": "marker",
        "session_id": session_id,
        "sequence": 1,
        "previous_entry_hash": start_body["entry_hash"],
        "client_clock_id": "clock-2",
        "client_monotonic_time": 0,
        "client_wall_time": "2026-07-30T15:00:01-03:00",
        "server_challenge": session["server_challenge"],
    }
    rejected_clock = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "invalid-clock"},
        json=signed_entry(invalid_clock_change),
    )
    assert rejected_clock.status_code == 422

    divergent = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "start-1"},
        json={**start_body, "entry_hash": "sha256:" + "0" * 64},
    )
    assert divergent.status_code == 409
    with client.app.state.session_factory() as database:
        assert database.scalar(
            select(Incident).where(
                Incident.session_id == session_id,
                Incident.kind == "event_idempotency_conflict",
            )
        )

    part_data = b"first video part"
    part_hash = sha256_identifier(part_data)
    part_entry = {
        "protocol_version": "0.1.0",
        "entry_type": "artifact_part",
        "session_id": session_id,
        "sequence": 1,
        "artifact_id": "recording",
        "part_number": 0,
        "part_hash": part_hash,
        "previous_entry_hash": start_body["entry_hash"],
        "client_clock_id": "clock-1",
        "client_monotonic_time": 1_000_000,
        "client_wall_time": "2026-07-30T15:00:01-03:00",
        "server_challenge": session["server_challenge"],
    }
    signed_part = signed_entry(part_entry)
    headers = {
        "Idempotency-Key": "part-1",
        "X-Entry-Json": base64url_encode(canonical_bytes(part_entry)),
        "X-Entry-Hash": signed_part["entry_hash"],
        "X-Entry-Signature": signed_part["signature_hex"],
        "Content-Type": "application/octet-stream",
    }
    uploaded = client.put(
        f"/v1/sessions/{session_id}/artifacts/recording/parts/0",
        headers=headers,
        content=part_data,
    )
    assert uploaded.status_code == 201
    receipt = uploaded.json()
    assert receipt["part_hash"] == part_hash
    assert receipt["persistence_state"] == "durable_staging"
    assert verify_canonical(
        DOMAINS["receipt"],
        receipt["receipt"],
        bytes.fromhex(receipt["receipt_signature_hex"]),
        public_key(SERVER_SEED),
    )
    replayed_part = client.put(
        f"/v1/sessions/{session_id}/artifacts/recording/parts/0",
        headers=headers,
        content=part_data,
    )
    assert replayed_part.status_code == 200
    assert replayed_part.json()["receipt_hash"] == receipt["receipt_hash"]

    divergent_part = client.put(
        f"/v1/sessions/{session_id}/artifacts/recording/parts/0",
        headers=headers,
        content=b"different bytes",
    )
    assert divergent_part.status_code == 409

    completed_entry = {
        "protocol_version": "0.1.0",
        "entry_type": "artifact_completed",
        "session_id": session_id,
        "sequence": 2,
        "artifact_id": "recording",
        "artifact_hash": part_hash,
        "previous_entry_hash": signed_part["entry_hash"],
        "client_clock_id": "clock-1",
        "client_monotonic_time": 2_000_000,
        "client_wall_time": "2026-07-30T15:00:02-03:00",
        "server_challenge": session["server_challenge"],
    }
    completed_body = {
        "entry": signed_entry(completed_entry),
        "part_count": 1,
        "size": len(part_data),
        "artifact_hash": part_hash,
        "path": "capture/recording.webm",
        "media_type": "video/webm",
        "method": "MediaRecorder",
        "provenance": "client_reported",
    }
    completed = client.post(
        f"/v1/sessions/{session_id}/artifacts/recording/complete",
        json=completed_body,
    )
    assert completed.status_code == 201
    assert completed.json()["artifact_hash"] == part_hash
    replayed_completion = client.post(
        f"/v1/sessions/{session_id}/artifacts/recording/complete",
        json=completed_body,
    )
    assert replayed_completion.status_code == 200

    finish_entry = {
        "protocol_version": "0.1.0",
        "entry_type": "capture_finished",
        "session_id": session_id,
        "sequence": 3,
        "previous_entry_hash": signed_entry(completed_entry)["entry_hash"],
        "client_clock_id": "clock-1",
        "client_monotonic_time": 3_000_000,
        "client_wall_time": "2026-07-30T15:00:03-03:00",
        "server_challenge": session["server_challenge"],
    }
    finish_body = signed_entry(finish_entry)
    finished = client.post(
        f"/v1/sessions/{session_id}/events",
        headers={"Idempotency-Key": "finish-1"},
        json=finish_body,
    )
    assert finished.status_code == 201

    capture_close = {
        "protocol_version": "0.1.0",
        "session_id": session_id,
        "session_root": finish_body["entry_hash"],
        "last_entry_hash": finish_body["entry_hash"],
        "entry_count": 4,
        "artifacts": [
            {
                "artifact_id": "recording",
                "path": "capture/recording.webm",
                "size": len(part_data),
                "status": "captured",
                "artifact_hash": part_hash,
            }
        ],
        "known_gaps": [],
        "client_key_id": "client-test",
        "client_public_key": base64url_encode(public_key(CLIENT_SEED)),
    }
    rejected_signature = client.post(
        f"/v1/sessions/{session_id}/finalize",
        json={"capture_close": capture_close, "signature_hex": "00" * 64},
    )
    assert rejected_signature.status_code == 422

    close_signature = sign_canonical(
        DOMAINS["capture_close"],
        capture_close,
        CLIENT_SEED,
    ).hex()
    finalized = client.post(
        f"/v1/sessions/{session_id}/finalize",
        json={"capture_close": capture_close, "signature_hex": close_signature},
    )
    assert finalized.status_code == 200
    result = finalized.json()
    assert result["status"] == "complete"
    Draft202012Validator(
        json.loads((SCHEMA_DIR / "capture-close.schema.json").read_text()),
        format_checker=FormatChecker(),
    ).validate(capture_close)
    Draft202012Validator(
        json.loads((SCHEMA_DIR / "manifest.schema.json").read_text()),
        format_checker=FormatChecker(),
    ).validate(result["manifest"])
    assert result["manifest_hash"] == sha256_identifier(
        canonical_bytes(result["manifest"])
    )
    assert verify_canonical(
        DOMAINS["manifest"],
        result["manifest"],
        bytes.fromhex(result["manifest_signature_hex"]),
        public_key(SERVER_SEED),
    )

    replayed_finalize = client.post(
        f"/v1/sessions/{session_id}/finalize",
        json={"capture_close": capture_close, "signature_hex": close_signature},
    )
    assert replayed_finalize.status_code == 200
    assert replayed_finalize.json() == result

    queued_job = client.post(
        f"/v1/sessions/{session_id}/timestamp-jobs",
        headers={"Idempotency-Key": "async-primary"},
    )
    assert queued_job.status_code == 202
    replayed_job = client.post(
        f"/v1/sessions/{session_id}/timestamp-jobs",
        headers={"Idempotency-Key": "async-primary"},
    )
    assert replayed_job.status_code == 202
    assert replayed_job.json() == queued_job.json()
    assert (
        client.get(f"/v1/jobs/{queued_job.json()['job_id']}").json()
        == queued_job.json()
    )

    timestamped = client.post(
        f"/v1/sessions/{session_id}/timestamp",
        headers={"Idempotency-Key": "timestamp-primary"},
    )
    assert timestamped.status_code == 200
    timestamp_attestation = timestamped.json()
    assert timestamp_attestation["document"]["manifest_hash"] == result["manifest_hash"]
    assert timestamp_attestation["document"]["timestamp_status"] == "pending"
    assert verify_canonical(
        DOMAINS["attestation"],
        timestamp_attestation["document"],
        bytes.fromhex(timestamp_attestation["signature_hex"]),
        public_key(SERVER_SEED),
    )
    retried_timestamp = client.post(f"/v1/sessions/{session_id}/timestamp")
    assert retried_timestamp.status_code == 200
    replayed_timestamp = client.post(
        f"/v1/sessions/{session_id}/timestamp",
        headers={"Idempotency-Key": "timestamp-primary"},
    )
    assert replayed_timestamp.status_code == 200
    assert replayed_timestamp.json() == timestamp_attestation
    with client.app.state.session_factory() as database:
        attempts = list(
            database.scalars(
                select(TimestampAttempt)
                .where(TimestampAttempt.session_id == session_id)
                .order_by(TimestampAttempt.attempt_number)
            )
        )
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]
        assert {attempt.manifest_hash for attempt in attempts} == {
            result["manifest_hash"]
        }
        jobs = list(
            database.scalars(
                select(Job)
                .where(Job.subject_id == session_id)
                .order_by(Job.created_at)
            )
        )
        assert len(jobs) == 3
        assert sum(job.status == "completed" and job.attempts == 1 for job in jobs) == 2
        assert sum(job.status == "pending" and job.attempts == 0 for job in jobs) == 1

    def fake_stamp(
        root_hash: str,
        root_file: Path,
        proof_file: Path,
        _calendars: list[str],
    ) -> None:
        root_file.parent.mkdir(parents=True, exist_ok=True)
        root_file.write_bytes(bytes.fromhex(root_hash[7:]))
        proof_file.write_bytes(b"immutable-original-proof")

    def fake_upgrade(original: Path, complement: Path) -> None:
        complement.parent.mkdir(parents=True, exist_ok=True)
        complement.write_bytes(original.read_bytes() + b"-confirmed")

    monkeypatch.setattr("chitaozinho_api.proof_service.stamp_ots", fake_stamp)
    monkeypatch.setattr("chitaozinho_api.proof_service.upgrade_ots", fake_upgrade)
    monkeypatch.setattr(
        "chitaozinho_api.proof_service.verify_ots",
        lambda _root, _proof: "confirmed",
    )
    batch = client.post(
        "/v1/merkle-batches",
        json={"session_ids": [session_id], "submit_ots": True},
    )
    assert batch.status_code == 201
    assert batch.json()["status"] == "pending_confirmation"
    batch_id = batch.json()["batch_id"]
    original_proof = tmp_path / "proofs" / "merkle" / batch_id / "root.bin.ots"
    original_bytes = original_proof.read_bytes()

    upgraded = client.post(f"/v1/merkle-batches/{batch_id}/upgrade")
    assert upgraded.status_code == 200
    assert upgraded.json()["status"] == "confirmed"
    assert original_proof.read_bytes() == original_bytes
    assert upgraded.json()["proof_hash"] != sha256_identifier(original_bytes)

    attestations = client.get(f"/v1/sessions/{session_id}/attestations")
    assert attestations.status_code == 200
    documents = attestations.json()
    assert len(documents) == 4
    assert (
        documents[3]["document"]["previous_attestation_hash"]
        == documents[2]["document_hash"]
    )
    attestation_schema = json.loads(
        (SCHEMA_DIR / "attestation.schema.json").read_text()
    )
    for attestation in documents:
        Draft202012Validator(
            attestation_schema,
            format_checker=FormatChecker(),
        ).validate(attestation["document"])
        assert verify_canonical(
            DOMAINS["attestation"],
            attestation["document"],
            bytes.fromhex(attestation["signature_hex"]),
            public_key(SERVER_SEED),
        )

    proof_bundle = client.get(f"/v1/sessions/{session_id}/proof-bundle")
    assert proof_bundle.status_code == 200
    assert proof_bundle.headers["X-Storage-Status"] == "stored"
    assert proof_bundle.headers["X-Proof-Bundle-SHA256"] == sha256_identifier(
        proof_bundle.content
    )
    with ZipFile(BytesIO(proof_bundle.content)) as archive:
        names = set(archive.namelist())
        assert {
            "attestations.jsonl",
            "proof-bundle-index.json",
            "signatures/proof-bundle-index.server.sig",
        }.issubset(names)
        proof_index = json.loads(archive.read("proof-bundle-index.json"))
        proof_index_signature = bytes.fromhex(
            archive.read("signatures/proof-bundle-index.server.sig")
            .decode()
            .strip()
        )
        assert proof_index["manifest_hash"] == result["manifest_hash"]
        assert verify_canonical(
            DOMAINS["proof_bundle_index"],
            proof_index,
            proof_index_signature,
            public_key(SERVER_SEED),
        )
        assert {member["path"] for member in proof_index["members"]} == names - {
            "proof-bundle-index.json",
            "signatures/proof-bundle-index.server.sig",
        }

    package = client.get(f"/v1/sessions/{session_id}/package")
    assert package.status_code == 200
    assert package.headers["content-type"] == "application/zip"
    assert package.headers["X-Storage-Status"] == "stored"
    package_hash = client.get(f"/v1/sessions/{session_id}/package.sha256")
    assert package_hash.status_code == 200
    assert package_hash.headers["content-type"].startswith("text/plain")
    assert (
        package_hash.headers["X-Package-SHA256"] == package.headers["X-Package-SHA256"]
    )
    assert package_hash.text == (
        f"{package.headers['X-Package-SHA256'].removeprefix('sha256:')}  "
        f"chitaozinho-{session_id}.zip\n"
    )
    package_path = tmp_path / "capture.zip"
    package_path.write_bytes(package.content)
    verified = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--bin",
            "chitaozinho-verify",
            "--",
            "verify",
            str(package_path),
            "--trusted-server-key-hex",
            public_key(SERVER_SEED).hex(),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["result"] == "integral"

    current = client.get(f"/v1/sessions/{session_id}")
    assert current.status_code == 200
    assert current.json()["next_sequence"] == 4
    assert current.json()["capture_status"] == "complete"
    assert current.json()["manifest_hash"] == result["manifest_hash"]
    assert current.json()["package_status"] == "available"
    assert current.json()["timestamp_status"] == "pending"
    assert current.json()["blockchain_status"] == "confirmed"
    assert current.json()["storage_status"] == "stored"

    with client.app.state.session_factory() as database:
        audit_events = list(
            database.scalars(select(AuditEvent).order_by(AuditEvent.sequence))
        )
        assert [event.sequence for event in audit_events] == list(
            range(len(audit_events))
        )
        previous_hash = None
        for audit_event in audit_events:
            created_at = audit_event.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
            document = {
                "schema_version": "0.1.0",
                "sequence": audit_event.sequence,
                "previous_event_hash": previous_hash,
                "event_type": audit_event.event_type,
                "subject_id": audit_event.subject_id,
                "details": audit_event.details,
                "created_at": created_at.isoformat().replace("+00:00", "Z"),
            }
            assert audit_event.previous_event_hash == previous_hash
            assert audit_event.event_hash == sha256_identifier(canonical_bytes(document))
            previous_hash = audit_event.event_hash

        audit_events[0].details = {"tampered": True}
        with pytest.raises(ValueError, match="append-only"):
            database.commit()
        database.rollback()


def test_artifact_identifier_cannot_escape_storage(client: TestClient) -> None:
    created = client.post("/v1/sessions").json()
    registered = client.post(
        f"/v1/sessions/{created['session_id']}/keys",
        json={
            "key_id": "client-test",
            "public_key": base64url_encode(public_key(CLIENT_SEED)),
        },
    )
    assert registered.status_code == 204
    response = client.put(
        f"/v1/sessions/{created['session_id']}/artifacts/../parts/0",
        headers={
            "Idempotency-Key": "unsafe",
            "X-Entry-Json": base64url_encode(b"{}"),
            "X-Entry-Hash": "sha256:" + "0" * 64,
            "X-Entry-Signature": "00" * 64,
        },
        content=b"bytes",
    )
    assert response.status_code in {404, 422}


def test_unavailable_artifact_produces_verifiable_incomplete_package(
    client: TestClient,
    tmp_path: Path,
) -> None:
    created = client.post("/v1/sessions").json()
    session_id = created["session_id"]
    assert (
        client.post(
            f"/v1/sessions/{session_id}/keys",
            json={
                "key_id": "client-test",
                "public_key": base64url_encode(public_key(CLIENT_SEED)),
            },
        ).status_code
        == 204
    )

    def entry(
        entry_type: str,
        sequence: int,
        previous_hash: str | None,
        **fields: object,
    ) -> dict:
        return {
            "protocol_version": "0.1.0",
            "entry_type": entry_type,
            "session_id": session_id,
            "sequence": sequence,
            "previous_entry_hash": previous_hash,
            "client_clock_id": "clock-partial",
            "client_monotonic_time": sequence * 1_000,
            "client_wall_time": f"2026-07-30T15:00:0{sequence}-03:00",
            "server_challenge": created["server_challenge"],
            **fields,
        }

    software_identity = {
        "name": "Chitãozinho Chromium Extension",
        "version": "0.1.0",
        "commit": "test-commit",
        "build_hash": "sha256:" + ("ab" * 32),
    }
    started = signed_entry(
        entry(
            "capture_started",
            0,
            None,
            event_data={"software": software_identity},
        )
    )
    assert (
        client.post(
            f"/v1/sessions/{session_id}/events",
            headers={"Idempotency-Key": "partial-start"},
            json=started,
        ).status_code
        == 201
    )
    reason = "protected browser page does not permit DOM access"
    unavailable = signed_entry(
        entry(
            "artifact_unavailable",
            1,
            started["entry_hash"],
            artifact_id="dom",
            event_data={"status": "unavailable", "reason": reason},
        )
    )
    declared = client.post(
        f"/v1/sessions/{session_id}/artifacts/dom/unavailable",
        json={
            "entry": unavailable,
            "path": "capture/dom.html",
            "media_type": "text/html",
            "method": "DOM serialization",
            "provenance": "client_reported",
            "status": "unavailable",
            "reason": reason,
        },
    )
    assert declared.status_code == 201
    assert declared.json()["artifact_hash"] is None

    finished = signed_entry(
        entry("capture_finished", 2, unavailable["entry_hash"])
    )
    assert (
        client.post(
            f"/v1/sessions/{session_id}/events",
            headers={"Idempotency-Key": "partial-finish"},
            json=finished,
        ).status_code
        == 201
    )
    artifacts = [
        {
            "artifact_id": "dom",
            "path": "capture/dom.html",
            "size": 0,
            "status": "unavailable",
            "reason": reason,
        }
    ]
    capture_close = {
        "protocol_version": "0.1.0",
        "session_id": session_id,
        "session_root": finished["entry_hash"],
        "last_entry_hash": finished["entry_hash"],
        "entry_count": 3,
        "artifacts": artifacts,
        "known_gaps": [f"dom: {reason}"],
        "client_key_id": "client-test",
        "client_public_key": base64url_encode(public_key(CLIENT_SEED)),
    }
    finalized = client.post(
        f"/v1/sessions/{session_id}/finalize",
        json={
            "capture_close": capture_close,
            "signature_hex": sign_canonical(
                DOMAINS["capture_close"],
                capture_close,
                CLIENT_SEED,
            ).hex(),
        },
    )
    assert finalized.status_code == 200
    assert finalized.json()["status"] == "incomplete"
    assert finalized.json()["manifest"]["capture"]["software"] == software_identity
    assert finalized.json()["manifest"]["artifacts"][0]["reason"] == reason
    assert "artifact_hash" not in finalized.json()["manifest"]["artifacts"][0]

    package = client.get(f"/v1/sessions/{session_id}/package")
    package_path = tmp_path / "partial.zip"
    package_path.write_bytes(package.content)
    with ZipFile(BytesIO(package.content)) as archive:
        assert "capture/dom.html" not in archive.namelist()
    verified = subprocess.run(
        [
            "cargo",
            "run",
            "--quiet",
            "--bin",
            "chitaozinho-verify",
            "--",
            "verify",
            str(package_path),
            "--trusted-server-key-hex",
            public_key(SERVER_SEED).hex(),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout)["result"] == "integral_but_incomplete"
    with client.app.state.session_factory() as database:
        audit_details = [
            event.details
            for event in database.scalars(
                select(AuditEvent).where(AuditEvent.subject_id == session_id)
            )
        ]
        assert reason not in json.dumps(audit_details)


def test_server_key_is_required_for_session_creation(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex=None,
    )
    client = TestClient(create_app(settings, create_tables=True))
    response = client.post("/v1/sessions")
    assert response.status_code == 503
