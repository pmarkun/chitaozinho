import json
import logging
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import chitaozinho_api.main as main_module
import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.jobs import get_or_create_job
from chitaozinho_api.main import (
    allowed_extension_origin_pattern,
    app,
    create_app,
    metrics_access_allowed,
)
from chitaozinho_api.security import ServerSigner
from chitaozinho_api.storage import LocalDurableStorage
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine


def test_healthz() -> None:
    response = TestClient(app).get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_metrics_and_logs_use_route_templates_without_sensitive_data(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    assert logging.getLogger("chitaozinho.request").level == logging.INFO
    caplog.set_level(logging.INFO, logger="chitaozinho.request")
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'observability.db'}",
        storage_path=tmp_path / "artifacts",
        server_seed_hex="11" * 32,
    )
    client = TestClient(create_app(settings, create_tables=True))
    response = client.get("/v1/sessions/private-session?token=top-secret&email=user@example.test")
    assert response.headers["X-Request-ID"]

    metrics = client.get("/metrics")
    assert metrics.status_code == 200
    assert 'route="/v1/sessions/{session_id}"' in metrics.text
    assert "private-session" not in metrics.text
    assert "top-secret" not in metrics.text
    assert "user@example.test" not in metrics.text
    assert 'chitaozinho_jobs{status="pending"} 0' in metrics.text
    assert "chitaozinho_jobs_ready 0" in metrics.text
    assert "chitaozinho_jobs_stale_running 0" in metrics.text

    now = datetime.now(UTC)
    with client.app.state.session_factory() as database:
        failed_job, _created = get_or_create_job(
            database,
            kind="synthetic_monitoring",
            idempotency_key="metrics-failed",
            subject_id=None,
            payload={},
        )
        failed_job.status = "failed"
        failed_job.available_at = now - timedelta(seconds=1)
        failed_job.updated_at = now
        running_job, _created = get_or_create_job(
            database,
            kind="synthetic_monitoring",
            idempotency_key="metrics-running",
            subject_id=None,
            payload={},
        )
        running_job.status = "running"
        running_job.available_at = now
        running_job.updated_at = now - timedelta(seconds=settings.worker_stale_seconds + 1)
        database.commit()

    job_metrics = client.get("/metrics")
    assert 'chitaozinho_jobs{status="failed"} 1' in job_metrics.text
    assert 'chitaozinho_jobs{status="running"} 1' in job_metrics.text
    assert "chitaozinho_jobs_ready 1" in job_metrics.text
    assert "chitaozinho_jobs_stale_running 1" in job_metrics.text

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "chitaozinho.request"
    ]
    assert any(record["route"] == "/v1/sessions/{session_id}" for record in records)
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


def test_public_metrics_require_dedicated_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    signer = ServerSigner.from_settings(
        Settings(
            server_key_id="server-metrics",
            server_seed_hex="11" * 32,
        )
    )
    assert signer is not None
    monkeypatch.setattr(
        main_module.ServerSigner,
        "from_settings",
        lambda _settings: signer,
    )
    settings = Settings.model_construct(
        env="staging",
        auth_mode="magic_link",
        public_base_url="https://api.example.test",
        metrics_token="m" * 32,
        extension_ids="abcdefghijklmnopabcdefghijklmnop",
    )
    client = TestClient(
        create_app(
            settings,
            engine=create_engine(f"sqlite:///{tmp_path / 'metrics.db'}"),
            storage=LocalDurableStorage(tmp_path / "artifacts"),
            magic_link_sender=lambda _email, _url: None,
            create_tables=True,
        )
    )

    missing = client.get("/metrics")
    wrong = client.get(
        "/metrics",
        headers={"Authorization": "Bearer " + ("x" * 32)},
    )
    accepted = client.get(
        "/metrics",
        headers={"Authorization": "Bearer " + ("m" * 32)},
    )

    assert missing.status_code == 401
    assert missing.headers["WWW-Authenticate"] == "Bearer"
    assert wrong.status_code == 401
    assert accepted.status_code == 200
    assert "chitaozinho_http_requests_total" in accepted.text


def test_non_local_environment_fails_closed_without_tls_and_external_storage() -> None:
    with pytest.raises(ValidationError, match="retry maximum"):
        Settings(
            worker_retry_base_seconds=10,
            worker_retry_max_seconds=5,
        )
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
    with pytest.raises(ValidationError, match="Ceph RGW"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
        )
    with pytest.raises(ValidationError, match="endpoint"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            storage_provider="ceph",
        )
    with pytest.raises(ValidationError, match="access credentials"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            storage_provider="ceph",
            s3_endpoint_url="https://rgw.example.test",
        )
    with pytest.raises(ValidationError, match="KMS"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            storage_provider="ceph",
            s3_endpoint_url="https://rgw.example.test",
            s3_access_key_id="access",
            s3_secret_access_key="secret",
        )
    with pytest.raises(ValidationError, match="PostgreSQL"):
        Settings(
            env="staging",
            public_base_url="https://example.test",
            storage_backend="s3",
            storage_provider="ceph",
            s3_endpoint_url="https://rgw.example.test",
            s3_access_key_id="access",
            s3_secret_access_key="secret",
            s3_kms_key_id="chitaozinho-evidence",
        )
    kms_storage = {
        "env": "staging",
        "public_base_url": "https://example.test",
        "database_url": "postgresql+psycopg://service@database/chitaozinho",
        "storage_backend": "s3",
        "storage_provider": "ceph",
        "s3_endpoint_url": "https://rgw.example.test",
        "s3_region": "ceph",
        "s3_access_key_id": "access",
        "s3_secret_access_key": "secret",
        "s3_kms_key_id": "chitaozinho-evidence",
    }
    with pytest.raises(ValidationError, match="Ceph RGW region"):
        Settings(**{**kms_storage, "s3_region": "garage"})
    with pytest.raises(ValidationError, match="HTTPS origin"):
        Settings(
            **{
                **kms_storage,
                "s3_endpoint_url": "http://127.0.0.1:3900",
            }
        )
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
        "server_seed_kms_key_id": ("arn:aws:kms:sa-east-1:123456789012:key/signing-envelope"),
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
    exact_extension_auth = {
        **public_auth,
        "extension_ids": "abcdefghijklmnopabcdefghijklmnop",
    }
    with pytest.raises(ValidationError, match="metrics bearer token"):
        Settings(**exact_extension_auth)
    public_observability = {
        **exact_extension_auth,
        "metrics_token": "m" * 32,
    }
    with pytest.raises(ValidationError, match="exact source commit"):
        Settings(**public_observability)
    with pytest.raises(ValidationError, match="non-zero SHA-256"):
        Settings(
            **public_observability,
            software_commit="a" * 40,
        )
    production_settings = Settings(
        **public_observability,
        software_commit="a" * 40,
        software_build_hash="sha256:" + ("b" * 64),
    )
    origin_pattern = re.compile(allowed_extension_origin_pattern(production_settings))
    assert origin_pattern.fullmatch("chrome-extension://abcdefghijklmnopabcdefghijklmnop")
    assert origin_pattern.fullmatch("chrome-extension://ponmlkjihgfedcbaponmlkjihgfedcba") is None
    assert metrics_access_allowed(production_settings, None) is False
    assert (
        metrics_access_allowed(
            production_settings,
            "Bearer " + ("x" * 32),
        )
        is False
    )
    assert metrics_access_allowed(
        production_settings,
        "Bearer " + ("m" * 32),
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
        metrics_token="metrics-secret-value-that-is-long",
    )

    rendered = repr(settings)
    assert "access-id" not in rendered
    assert "storage-secret" not in rendered
    assert ("11" * 32) not in rendered
    assert "pepper-secret" not in rendered
    assert "smtp-secret" not in rendered
    assert "metrics-secret" not in rendered


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
