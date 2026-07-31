import json
import logging
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import app, create_app
from chitaozinho_api.storage import LocalDurableStorage
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_healthz() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_and_logs_use_route_templates_without_sensitive_data(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    caplog.set_level(logging.INFO, logger="chitaozinho.request")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'observability.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex="11" * 32,
    )
    client = TestClient(create_app(settings, create_tables=True))
    response = client.get(
        "/v1/sessions/private-session?token=top-secret&email=user@example.test"
    )
    assert response.headers["X-Request-ID"]

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'route="/v1/sessions/{session_id}"' in metrics.text
    assert "private-session" not in metrics.text
    assert "top-secret" not in metrics.text
    assert "user@example.test" not in metrics.text

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "chitaozinho.request"
    ]
    assert any(
        record["route"] == "/v1/sessions/{session_id}" for record in records
    )
    serialized = json.dumps(records)
    assert "private-session" not in serialized
    assert "top-secret" not in serialized
    assert "user@example.test" not in serialized


def test_readyz_checks_database_and_storage(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'ready.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex="11" * 32,
    )
    client = TestClient(create_app(settings, create_tables=True))
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}

    class UnavailableStorage(LocalDurableStorage):
        def check_ready(self) -> None:
            raise RuntimeError("synthetic storage failure")

    unavailable = TestClient(
        create_app(
            settings,
            storage=UnavailableStorage(tmp_path / "unavailable"),
            create_tables=True,
        )
    ).get("/readyz")
    assert unavailable.status_code == 503
    assert unavailable.json() == {"status": "unavailable"}


def test_extension_cors_preflight() -> None:
    client = TestClient(app)
    response = client.options(
        "/v1/sessions",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"].startswith("chrome-extension://")
    assert response.headers["access-control-allow-credentials"] == "true"


def test_non_local_environment_fails_closed_without_tls_and_external_storage() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(env="staging", public_base_url="http://example.test")
    with pytest.raises(ValidationError, match="external S3"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="local",
        )
    with pytest.raises(ValidationError, match="KMS"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
        )
    kms_storage = {
        "env": "staging",
        "public_base_url": "https://example.test",
        "storage_backend": "s3",
        "s3_kms_key_id": "arn:aws:kms:sa-east-1:123456789012:key/evidence",
    }
    with pytest.raises(ValidationError, match="plaintext"):
        Settings(
            **kms_storage,
            server_seed_hex="11" * 32,
        )
    with pytest.raises(ValidationError, match="KMS-encrypted"):
        Settings(**kms_storage)
    signing_envelope = {
        "server_seed_kms_ciphertext_b64": "c3ludGhldGljLWNpcGhlcnRleHQ=",
        "server_seed_kms_key_id": (
            "arn:aws:kms:sa-east-1:123456789012:key/signing-envelope"
        ),
    }
    with pytest.raises(ValidationError, match="revocation list"):
        Settings(
            **kms_storage,
            **signing_envelope,
            server_certificate_path=Path("server-certificate.json"),
        )
    production_base = {
        **kms_storage,
        **signing_envelope,
        "server_certificate_path": Path("server-certificate.json"),
        "server_revocation_list_path": Path("key-revocations.json"),
        "server_root_public_path": Path("root-public.json"),
    }
    with pytest.raises(ValidationError, match="magic-link"):
        Settings(**production_base)
    with pytest.raises(ValidationError, match="token pepper"):
        Settings(**production_base, auth_mode="magic_link")
    with pytest.raises(ValidationError, match="SMTP"):
        Settings(
            **production_base,
            auth_mode="magic_link",
            auth_token_pepper="x" * 32,
        )
    with pytest.raises(ValidationError, match="only one server certificate"):
        Settings(
            server_certificate_path=Path("server-certificate.json"),
            server_certificate_json="{}",
        )


def test_settings_repr_redacts_credentials_and_key_material() -> None:
    settings = Settings(
        s3_access_key_id="access-id",
        s3_secret_access_key="storage-secret",
        server_seed_hex="11" * 32,
        auth_token_pepper="pepper-secret-value-that-is-long",
        smtp_password="smtp-secret",
    )

    rendered = repr(settings)
    assert "access-id" not in rendered
    assert "storage-secret" not in rendered
    assert ("11" * 32) not in rendered
    assert "pepper-secret" not in rendered
    assert "smtp-secret" not in rendered


def test_api_enforces_request_rate_limit(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'rate.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex=("11" * 32),
        requests_per_minute=1,
    )
    client = TestClient(create_app(settings, create_tables=True))
    assert client.post("/v1/sessions").status_code == 201
    limited = client.post("/v1/sessions")
    assert limited.status_code == 429
    assert limited.headers["Retry-After"] == "60"
