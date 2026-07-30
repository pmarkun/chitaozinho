from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.main import app, create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def test_healthz() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_non_local_environment_fails_closed_without_tls_and_external_storage() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        Settings(env="staging", public_base_url="http://example.test")
    with pytest.raises(ValidationError, match="external S3"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="local",
        )
    with pytest.raises(ValidationError, match="revocation list"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            server_seed_hex="11" * 32,
            server_certificate_path=Path("server-certificate.json"),
        )


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
