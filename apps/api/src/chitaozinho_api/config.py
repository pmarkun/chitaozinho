from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHITAOZINHO_",
        env_file=".env",
        extra="ignore",
    )

    env: str = "development"
    database_url: str = "sqlite:///data/chitaozinho.db"
    storage_backend: str = "local"
    storage_path: Path = Path("data/artifacts")
    proofs_path: Path = Path("data/proofs")
    s3_endpoint_url: str | None = None
    s3_region: str = "garage"
    s3_bucket: str = "chitaozinho"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    server_key_id: str = "server-unconfigured"
    server_seed_hex: str | None = Field(default=None, min_length=64, max_length=64)
    server_certificate_path: Path | None = None
    public_base_url: str = "http://127.0.0.1:8000"
    cors_origin_regex: str = r"^chrome-extension://[a-p]{32}$"
    max_part_size: int = 8 * 1024 * 1024
    max_artifact_parts: int = 10_000
    max_artifact_size: int = 2 * 1024 * 1024 * 1024
    max_session_size: int = 5 * 1024 * 1024 * 1024
    max_session_duration_seconds: int = 2 * 60 * 60
    requests_per_minute: int = 600
    worker_poll_seconds: float = 2.0
    worker_stale_seconds: int = 5 * 60
    software_name: str = "Chitãozinho Client"
    software_version: str = "0.1.0"
    software_commit: str = "development"
    software_build_hash: str = "sha256:" + ("0" * 64)
    tsa_url: str | None = None
    tsa_ca_bundle: Path | None = None
    tsa_untrusted_chain: Path | None = None
    tsa_crl_bundle: Path | None = None
    ots_calendars: str = (
        "https://alice.btc.calendar.opentimestamps.org,"
        "https://bob.btc.calendar.opentimestamps.org"
    )

    @model_validator(mode="after")
    def production_safety(self) -> Settings:
        if self.env not in {"development", "test"}:
            if not self.public_base_url.startswith("https://"):
                raise ValueError("HTTPS public_base_url is required outside local development")
            if self.storage_backend != "s3":
                raise ValueError("external S3 storage is required outside local development")
            if self.server_seed_hex is None:
                raise ValueError("server signing key is required outside local development")
            if self.server_certificate_path is None:
                raise ValueError(
                    "root-signed server certificate is required outside local development"
                )
        return self
