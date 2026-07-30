from __future__ import annotations

from pathlib import Path

from pydantic import Field
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
    s3_endpoint_url: str | None = None
    s3_region: str = "garage"
    s3_bucket: str = "chitaozinho"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    server_key_id: str = "server-unconfigured"
    server_seed_hex: str | None = Field(default=None, min_length=64, max_length=64)
    public_base_url: str = "http://127.0.0.1:8000"
    cors_origin_regex: str = r"^chrome-extension://[a-p]{32}$"
    max_part_size: int = 8 * 1024 * 1024
    max_artifact_parts: int = 10_000
    software_name: str = "Chitãozinho Client"
    software_version: str = "0.1.0"
    software_commit: str = "development"
    software_build_hash: str = "sha256:" + ("0" * 64)
    tsa_url: str | None = None
    tsa_ca_bundle: Path | None = None
    tsa_untrusted_chain: Path | None = None
    ots_calendars: str = (
        "https://alice.btc.calendar.opentimestamps.org,"
        "https://bob.btc.calendar.opentimestamps.org"
    )
