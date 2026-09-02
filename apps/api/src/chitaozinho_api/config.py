from __future__ import annotations

from os import environ
from pathlib import Path
from re import fullmatch
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CHITAOZINHO_",
        env_file=".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    env: Literal["development", "test", "beta", "staging", "production"] = "development"
    database_url: str = "sqlite:///data/chitaozinho.db"
    storage_backend: str = "local"
    storage_provider: Literal["local", "garage", "railway", "ceph"] = "local"
    storage_path: Path = Path("data/artifacts")
    proofs_path: Path = Path("data/proofs")
    s3_endpoint_url: str | None = None
    s3_region: str = "ceph"
    s3_bucket: str = "chitaozinho"
    s3_access_key_id: str | None = Field(default=None, repr=False)
    s3_secret_access_key: str | None = Field(default=None, repr=False)
    s3_kms_key_id: str | None = None
    s3_ca_bundle: Path | None = None
    server_key_id: str = "server-unconfigured"
    server_seed_hex: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        repr=False,
    )
    server_seed_path: Path | None = None
    openbao_addr: str | None = None
    openbao_token: str | None = Field(default=None, min_length=16, repr=False)
    openbao_role_id: str | None = Field(default=None, min_length=8, repr=False)
    openbao_secret_id: str | None = Field(default=None, min_length=8, repr=False)
    openbao_transit_mount: str = Field(
        default="transit",
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    openbao_transit_key: str | None = Field(
        default=None,
        pattern=r"^[a-zA-Z0-9_-]+$",
    )
    openbao_transit_key_version: int | None = Field(default=None, ge=1)
    openbao_ca_bundle: Path | None = None
    server_certificate_path: Path | None = None
    server_certificate_json: str | None = Field(
        default=None,
        max_length=65_536,
        repr=False,
    )
    server_revocation_list_path: Path | None = None
    server_revocation_list_json: str | None = Field(
        default=None,
        max_length=1_048_576,
        repr=False,
    )
    server_root_public_path: Path | None = None
    server_root_public_json: str | None = Field(
        default=None,
        max_length=16_384,
        repr=False,
    )
    public_base_url: str = "http://127.0.0.1:8000"
    auth_mode: str = "development"
    auth_token_pepper: str | None = Field(default=None, min_length=32, repr=False)
    magic_link_ttl_seconds: int = Field(default=15 * 60, ge=60, le=60 * 60)
    access_token_ttl_seconds: int = Field(
        default=30 * 24 * 60 * 60,
        ge=5 * 60,
        le=365 * 24 * 60 * 60,
    )
    download_url_ttl_seconds: int = Field(default=5 * 60, ge=60, le=60 * 60)
    smtp_host: str | None = None
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: str | None = Field(default=None, repr=False)
    smtp_from: str | None = None
    smtp_starttls: bool = True
    email_provider: Literal["smtp", "resend"] = "smtp"
    resend_api_key: str | None = Field(default=None, min_length=16, repr=False)
    resend_from: str | None = None
    magic_link_email_limit_per_hour: int = Field(default=5, ge=1, le=100)
    magic_link_ip_limit_per_hour: int = Field(default=20, ge=1, le=1000)
    extension_ids: str = ""
    cors_origin_regex: str = r"^chrome-extension://[a-p]{32}$"
    metrics_token: str | None = Field(default=None, min_length=32, repr=False)
    max_part_size: int = 8 * 1024 * 1024
    max_artifact_parts: int = 10_000
    max_artifact_size: int = 2 * 1024 * 1024 * 1024
    max_session_size: int = 5 * 1024 * 1024 * 1024
    max_session_duration_seconds: int = 2 * 60 * 60
    retention_days: int = Field(default=90, ge=1, le=36500)
    requests_per_minute: int = 600
    worker_poll_seconds: float = 2.0
    worker_stale_seconds: int = 5 * 60
    worker_retry_base_seconds: float = Field(default=5.0, ge=0.1, le=3600)
    worker_retry_max_seconds: float = Field(default=3600.0, ge=1, le=86400)
    software_name: str = "Chitãozinho Client"
    software_version: str = "0.1.0"
    software_commit: str = Field(
        default_factory=lambda: environ.get("RAILWAY_GIT_COMMIT_SHA", "development")
    )
    software_build_hash: str = "sha256:" + ("0" * 64)
    software_build_hash_path: Path | None = None
    tsa_url: str | None = None
    tsa_ca_bundle: Path | None = None
    tsa_untrusted_chain: Path | None = None
    tsa_crl_bundle: Path | None = None
    ots_calendars: str = (
        "https://alice.btc.calendar.opentimestamps.org,https://bob.btc.calendar.opentimestamps.org"
    )

    @model_validator(mode="after")
    def production_safety(self) -> Settings:
        if self.software_build_hash_path is not None:
            try:
                build_hash = self.software_build_hash_path.read_text(encoding="ascii").strip()
            except (OSError, UnicodeError) as error:
                raise ValueError("software build identity file is unreadable") from error
            object.__setattr__(self, "software_build_hash", build_hash)
        if self.worker_retry_max_seconds < self.worker_retry_base_seconds:
            raise ValueError("worker retry maximum must not be shorter than its base delay")
        if self.env not in {"development", "test"}:
            if not self.public_base_url.startswith("https://"):
                raise ValueError("HTTPS public_base_url is required outside local development")
            if self.storage_backend != "s3":
                raise ValueError("external S3 storage is required outside local development")
            expected_provider = "railway" if self.env == "beta" else "ceph"
            if self.storage_provider != expected_provider:
                if expected_provider == "ceph":
                    raise ValueError("Ceph RGW is required outside local development")
                raise ValueError("Railway Bucket storage is required in beta")
            if self.s3_endpoint_url is None:
                raise ValueError("S3 endpoint is required outside local development")
            endpoint = urlsplit(self.s3_endpoint_url)
            if (
                endpoint.scheme != "https"
                or endpoint.hostname is None
                or endpoint.username is not None
                or endpoint.password is not None
                or endpoint.path not in {"", "/"}
                or endpoint.query
                or endpoint.fragment
            ):
                raise ValueError("S3 endpoint must be an HTTPS origin")
            if self.s3_access_key_id is None or self.s3_secret_access_key is None:
                raise ValueError("S3 access credentials are required outside local development")
            if self.env != "beta" and self.s3_kms_key_id is None:
                raise ValueError("Ceph RGW SSE-KMS key is required outside local development")
            if make_url(self.database_url).get_backend_name() != "postgresql":
                raise ValueError("PostgreSQL database is required outside local development")
            if self.env != "beta" and self.s3_region != "ceph":
                raise ValueError("evidence storage must use the Ceph RGW region")
            if self.env == "beta" and self.retention_days != 30:
                raise ValueError("beta retention must be exactly 30 days")
            if self.env != "beta" and self.retention_days < 90:
                raise ValueError("staging and production retention must be at least 90 days")
            if self.server_seed_hex is not None:
                raise ValueError(
                    "plaintext server signing seed is forbidden outside local development"
                )
            if (
                self.openbao_addr is None
                or self.openbao_role_id is None
                or self.openbao_secret_id is None
                or self.openbao_transit_key is None
                or self.openbao_transit_key_version is None
            ):
                raise ValueError(
                    "OpenBao AppRole Transit signing is required outside local development"
                )
            if self.openbao_token is not None:
                raise ValueError("static OpenBao tokens are forbidden outside local development")
            openbao = urlsplit(self.openbao_addr)
            if (
                openbao.scheme != "https"
                or openbao.hostname is None
                or openbao.username is not None
                or openbao.password is not None
                or openbao.path not in {"", "/"}
                or openbao.query
                or openbao.fragment
            ):
                raise ValueError("OpenBao address must be an HTTPS origin")
            if self.server_seed_path is not None:
                raise ValueError("server signing key material must remain in OpenBao Transit")
            if self.server_certificate_path is None and self.server_certificate_json is None:
                raise ValueError(
                    "root-signed server certificate is required outside local development"
                )
            if (
                self.server_revocation_list_path is None
                and self.server_revocation_list_json is None
            ):
                raise ValueError(
                    "root-signed key revocation list is required outside local development"
                )
            if self.server_root_public_path is None and self.server_root_public_json is None:
                raise ValueError("offline root public key is required outside local development")
            if self.auth_mode != "magic_link":
                raise ValueError("magic-link authentication is required outside local development")
            if self.auth_token_pepper is None:
                raise ValueError(
                    "authentication token pepper is required outside local development"
                )
            if self.email_provider == "smtp":
                if self.smtp_host is None or self.smtp_from is None:
                    raise ValueError("SMTP host and sender are required outside local development")
                if not self.smtp_starttls:
                    raise ValueError("SMTP STARTTLS is required outside local development")
            elif self.resend_api_key is None or self.resend_from is None:
                raise ValueError("Resend API key and sender are required")
            if not self.parsed_extension_ids():
                raise ValueError(
                    "at least one exact Chromium extension ID is required outside local development"
                )
            if self.metrics_token is None:
                raise ValueError("metrics bearer token is required outside local development")
            if fullmatch(r"[0-9a-f]{40,64}", self.software_commit) is None:
                raise ValueError("exact source commit is required outside local development")
            if fullmatch(
                r"sha256:[0-9a-f]{64}", self.software_build_hash
            ) is None or self.software_build_hash == "sha256:" + ("0" * 64):
                raise ValueError(
                    "non-zero SHA-256 build identity is required outside local development"
                )
        elif self.auth_mode not in {"development", "magic_link"}:
            raise ValueError("unsupported authentication mode")
        openbao_values = [
            self.openbao_addr,
            self.openbao_transit_key,
            self.openbao_transit_key_version,
        ]
        if any(value is not None for value in openbao_values) and not all(
            value is not None for value in openbao_values
        ):
            raise ValueError("OpenBao Transit signing configuration is incomplete")
        if (self.openbao_role_id is None) != (self.openbao_secret_id is None):
            raise ValueError("OpenBao AppRole configuration is incomplete")
        if self.openbao_token is not None and self.openbao_role_id is not None:
            raise ValueError("configure only one OpenBao authentication method")
        if self.openbao_addr is not None and not (
            self.openbao_token is not None or self.openbao_role_id is not None
        ):
            raise ValueError("OpenBao authentication is not configured")
        seed_sources = [
            self.server_seed_hex is not None,
            self.server_seed_path is not None,
            self.openbao_addr is not None,
        ]
        if sum(seed_sources) > 1:
            raise ValueError("configure only one server signing seed source")
        trust_sources = [
            (
                self.server_certificate_path,
                self.server_certificate_json,
                "server certificate",
            ),
            (
                self.server_revocation_list_path,
                self.server_revocation_list_json,
                "server revocation list",
            ),
            (
                self.server_root_public_path,
                self.server_root_public_json,
                "server root public key",
            ),
        ]
        for path, inline, label in trust_sources:
            if path is not None and inline is not None:
                raise ValueError(f"configure only one {label} source")
        return self

    def parsed_extension_ids(self) -> tuple[str, ...]:
        values = tuple(value.strip() for value in self.extension_ids.split(",") if value.strip())
        if any(fullmatch(r"[a-p]{32}", value) is None for value in values):
            raise ValueError("invalid Chromium extension ID")
        if len(set(values)) != len(values):
            raise ValueError("duplicate Chromium extension ID")
        return values
