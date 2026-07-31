import json
import logging
import re
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import allowed_extension_origin_pattern, app, create_app
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
    assert logging.getLogger("chitaozinho.request").isEnabledFor(logging.INFO)
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
    with pytest.raises(ValidationError, match="development.*test.*staging.*production"):
        Settings(env="preview")  # type: ignore[arg-type]
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
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            s3_kms_key_id="arn:aws:kms:sa-east-1:123456789012:key/evidence",
        )
    kms_storage = {
        "env": "staging",
        "public_base_url": "https://example.test",
        "database_url": "postgresql+psycopg://service@database/chitaozinho",
        "storage_backend": "s3",
        "s3_region": "sa-east-1",
        "s3_kms_key_id": "arn:aws:kms:sa-east-1:123456789012:key/evidence",
    }
    with pytest.raises(ValidationError, match="sa-east-1"):
        Settings(**{**kms_storage, "s3_region": "us-east-1"})
    with pytest.raises(ValidationError, match="custom S3 endpoints"):
        Settings(**kms_storage, s3_endpoint_url="http://127.0.0.1:3900")
    with pytest.raises(ValidationError, match="at least 90 days"):
        Settings(**kms_storage, retention_days=1)
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
    public_auth = {
        **production_base,
        "auth_mode": "magic_link",
        "auth_token_pepper": "x" * 32,
        "smtp_host": "smtp.example.test",
        "smtp_from": "capture@example.test",
    }
    with pytest.raises(ValidationError, match="extension ID"):
        Settings(**public_auth)
    with pytest.raises(ValidationError, match="invalid Chromium extension ID"):
        Settings(**public_auth, extension_ids="not-an-extension")
    production_settings = Settings(
        **public_auth,
        extension_ids="abcdefghijklmnopabcdefghijklmnop",
    )
    origin_pattern = re.compile(
        allowed_extension_origin_pattern(production_settings)
    )
    assert origin_pattern.fullmatch(
        "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
    )
    assert origin_pattern.fullmatch(
        "chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba"
    ) is None
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


def test_empty_optional_environment_value_is_not_treated_as_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHITAOZINHO_S3_KMS_KEY_ID", "")

    settings = Settings(_env_file=None)

    assert settings.s3_kms_key_id is None


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
