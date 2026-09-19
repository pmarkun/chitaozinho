from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from zipfile import ZipFile

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import create_app
from chitaozinho_api.models import ArtifactPart, CaptureSession
from chitaozinho_api.proof_service import timestamp_capture
from chitaozinho_api.security import ServerSigner
from chitaozinho_protocol import (
    DOMAINS,
    base64url_decode,
    base64url_encode,
    canonical_bytes,
    sha256_identifier,
    sign_canonical,
    verify_canonical,
)
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_capture_flow import CLIENT_SEED, SERVER_SEED, public_key, signed_entry


def test_hash_only_capture_never_stores_evidence(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        evidence_mode="hash_only",
        storage_path=tmp_path / "evidence",
        proofs_path=tmp_path / "proofs",
        server_key_id="test-key",
        server_seed_hex=SERVER_SEED.hex(),
    )
    client = TestClient(create_app(settings, create_tables=True))
    created = client.post("/v1/sessions").json()
    sid = created["session_id"]
    assert created["upload_policy"]["evidence_mode"] == "hash_only"
    assert created["retention_policy"]["mode"] == "client_only"
    assert client.get("/readyz").status_code == 200
    assert (
        client.post(
            f"/v1/sessions/{sid}/keys",
            json={
                "key_id": "client-test",
                "public_key": base64url_encode(public_key(CLIENT_SEED)),
            },
        ).status_code
        == 204
    )
    previous = None
    sequence = 0

    def entry(kind: str, **extra) -> dict:
        nonlocal sequence, previous
        signed = signed_entry(
            {
                "protocol_version": "0.1.0",
                "entry_type": kind,
                "session_id": sid,
                "sequence": sequence,
                "previous_entry_hash": previous,
                "client_clock_id": "clock",
                "client_monotonic_time": sequence,
                "client_wall_time": "2026-09-18T12:00:00Z",
                "server_challenge": created["server_challenge"],
                **extra,
            }
        )
        previous = signed["entry_hash"]
        sequence += 1
        return signed

    commitment = {"commitment": sha256_identifier(b"private title https://secret.invalid")}
    start = entry("capture_started", event_data=commitment)
    rejected = {**start, "entry": {**start["entry"], "event_data": {"url": "private"}}}
    assert (
        client.post(
            f"/v1/sessions/{sid}/events", json=rejected, headers={"Idempotency-Key": "start"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/sessions/{sid}/events", json=start, headers={"Idempotency-Key": "start"}
        ).status_code
        == 201
    )
    content = b'{"url":"https://private.invalid","text":"SENSITIVE_EVIDENCE_SENTINEL"}'
    digest = sha256_identifier(content)
    part = entry("artifact_part", artifact_id="metadata", part_number=0, part_hash=digest)
    headers = {
        "Idempotency-Key": "metadata-0",
        "X-Entry-Json": base64url_encode(canonical_bytes(part["entry"])),
        "X-Entry-Hash": part["entry_hash"],
        "X-Entry-Signature": part["signature_hex"],
    }
    part_url = f"/v1/sessions/{sid}/artifacts/metadata/parts/0"
    assert client.put(part_url, content=content, headers=headers).status_code == 409
    declaration = {"size": len(content), "part_hash": digest}
    registered = client.put(part_url + "/hash", json=declaration, headers=headers)
    assert registered.status_code == 201, registered.text
    receipt = registered.json()["receipt"]
    assert receipt["persistence_state"] == "hash_registered"
    assert receipt["protocol_version"] == "0.2.0"
    assert client.put(part_url + "/hash", json=declaration, headers=headers).status_code == 200
    assert (
        client.put(part_url + "/hash", json={**declaration, "size": 0}, headers=headers).status_code
        == 409
    )
    assert (
        client.put(
            part_url + "/hash", json={**declaration, "bytes": "secret"}, headers=headers
        ).status_code
        == 422
    )
    completed = entry(
        "artifact_completed", artifact_id="metadata", artifact_hash=digest, event_data=commitment
    )
    result = client.post(
        f"/v1/sessions/{sid}/artifacts/metadata/complete",
        json={
            "entry": completed,
            "part_count": 1,
            "size": len(content),
            "artifact_hash": digest,
            "path": "capture/metadata.json",
            "media_type": "application/json",
            "method": "browser metadata",
            "provenance": "client_reported",
        },
    )
    assert result.status_code == 201, result.text
    finish = entry("capture_finished", event_data=commitment)
    assert (
        client.post(
            f"/v1/sessions/{sid}/events", json=finish, headers={"Idempotency-Key": "finish"}
        ).status_code
        == 201
    )
    close = {
        "protocol_version": "0.1.0",
        "session_id": sid,
        "session_root": previous,
        "last_entry_hash": previous,
        "entry_count": sequence,
        "client_key_id": "client-test",
        "client_public_key": base64url_encode(public_key(CLIENT_SEED)),
        "known_gaps": [],
        "artifacts": [
            {
                "artifact_id": "metadata",
                "path": "capture/metadata.json",
                "size": len(content),
                "status": "captured",
                "artifact_hash": digest,
            }
        ],
    }
    result = client.post(
        f"/v1/sessions/{sid}/finalize",
        json={
            "capture_close": close,
            "signature_hex": sign_canonical(DOMAINS["capture_close"], close, CLIENT_SEED).hex(),
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["storage_status"] == "hash_only"
    manifest_hash = result.json()["manifest_hash"]
    public_status = client.get(f"/v1/public/proofs/{sid}", params={"manifest_hash": manifest_hash})
    assert public_status.status_code == 200
    assert public_status.json()["bundle_available"] is False
    assert (
        client.get(
            f"/v1/public/proofs/{sid}", params={"manifest_hash": "sha256:" + "0" * 64}
        ).status_code
        == 404
    )
    template = client.get(f"/v1/sessions/{sid}/local-package").json()
    assert "SENSITIVE_EVIDENCE_SENTINEL" not in json.dumps(template)
    members = {name: base64url_decode(data) for name, data in template["members"].items()}
    index = json.loads(members["package-index.json"])
    assert verify_canonical(
        DOMAINS["package_index"],
        index,
        bytes.fromhex(members["signatures/package-index.server.sig"].decode().strip()),
        public_key(SERVER_SEED),
    )
    assert client.post(f"/v1/sessions/{sid}/download-urls").status_code == 409
    assert client.get(f"/v1/sessions/{sid}/package").status_code == 409
    with client.app.state.session_factory() as db:
        saved = db.scalar(select(ArtifactPart))
        assert saved.storage_key == ""
        capture = db.get(CaptureSession, sid)
        assert capture.storage_expires_at is None
        assert capture.evidence_mode == "hash_only"
    assert not settings.storage_path.exists()
    assert b"SENSITIVE_EVIDENCE_SENTINEL" not in (tmp_path / "db.sqlite").read_bytes()
    assert b"private.invalid" not in (tmp_path / "db.sqlite").read_bytes()
    with client.app.state.session_factory() as db:
        timestamp_capture(
            db, settings, ServerSigner.from_settings(settings), db.get(CaptureSession, sid)
        )
    public_status = client.get(f"/v1/public/proofs/{sid}", params={"manifest_hash": manifest_hash})
    assert public_status.status_code == 200
    assert public_status.json()["bundle_available"] is True
    public_bundle = client.get(
        f"/v1/public/proofs/{sid}/bundle", params={"manifest_hash": manifest_hash}
    )
    assert public_bundle.status_code == 200
    assert public_bundle.headers["X-Storage-Status"] == "hash_only"
    proof_bundle = client.get(f"/v1/sessions/{sid}/proof-bundle")
    assert proof_bundle.status_code == 200, proof_bundle.text
    assert proof_bundle.headers["X-Storage-Status"] == "hash_only"
    assert not settings.storage_path.exists()

    # Optional cross-runtime fixture, containing only synthetic evidence.
    if fixture_dir := os.environ.get("HASH_ONLY_TEST_OUTPUT"):
        root = Path(fixture_dir)
        root.mkdir(parents=True, exist_ok=True)
        (root / "template.json").write_text(
            json.dumps(
                {
                    "template": template,
                    "content": base64.b64encode(content).decode(),
                    "part": part,
                    "server_key": public_key(SERVER_SEED).hex(),
                }
            )
        )
        members["capture/metadata.json"] = content
        with ZipFile(root / "evidence.zip", "w") as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        (root / "evidence.zip.sha256").write_text(
            sha256_identifier((root / "evidence.zip").read_bytes())[7:]
        )


@pytest.mark.parametrize("mode", ["remote", "hash_only"])
def test_unknown_custody_mode_rejected(mode: str) -> None:
    assert Settings(evidence_mode=mode).evidence_mode == mode
    with pytest.raises(ValueError):
        Settings(evidence_mode="none")
