from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import create_app
from chitaozinho_api.models import Incident
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

    package = client.get(f"/v1/sessions/{session_id}/package")
    assert package.status_code == 200
    assert package.headers["content-type"] == "application/zip"
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


def test_server_key_is_required_for_session_creation(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'api.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex=None,
    )
    client = TestClient(create_app(settings, create_tables=True))
    response = client.post("/v1/sessions")
    assert response.status_code == 503
