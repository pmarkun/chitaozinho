from __future__ import annotations

import base64
import json
import stat
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from chitaozinho_protocol import DOMAINS, sign_canonical, verify_canonical
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import Settings


@dataclass(frozen=True)
class ServerSigner:
    key_id: str
    private_seed: bytes = field(repr=False)
    public_key: bytes
    certificate: dict | None
    revocation_list: dict | None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        kms_client: Any | None = None,
        now: datetime | None = None,
    ) -> ServerSigner | None:
        if (
            settings.server_seed_hex is None
            and settings.server_seed_path is None
            and settings.server_seed_kms_ciphertext_b64 is None
        ):
            return None
        if settings.server_seed_hex is not None:
            seed = bytes.fromhex(settings.server_seed_hex)
        elif settings.server_seed_path is not None:
            seed = load_private_seed(settings.server_seed_path)
        else:
            if settings.server_seed_kms_key_id is None:
                raise ValueError("KMS key id is required for encrypted server seed")
            try:
                ciphertext = base64.b64decode(
                    settings.server_seed_kms_ciphertext_b64,
                    validate=True,
                )
            except (ValueError, TypeError) as error:
                raise ValueError("invalid KMS server seed ciphertext encoding") from error
            client = kms_client or boto3.client(
                "kms",
                region_name=settings.server_seed_kms_region,
                aws_access_key_id=settings.s3_access_key_id,
                aws_secret_access_key=settings.s3_secret_access_key,
            )
            response = client.decrypt(
                CiphertextBlob=ciphertext,
                KeyId=settings.server_seed_kms_key_id,
                EncryptionAlgorithm="SYMMETRIC_DEFAULT",
                EncryptionContext=server_seed_encryption_context(settings.server_key_id),
            )
            if response.get("KeyId") != settings.server_seed_kms_key_id:
                raise ValueError("KMS decrypted server seed with an unexpected key")
            seed = response.get("Plaintext")
            if not isinstance(seed, bytes):
                raise ValueError("KMS did not return server seed plaintext")
        if len(seed) != 32:
            raise ValueError("server signing seed must contain exactly 32 bytes")
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        certificate = load_json_document(
            settings.server_certificate_path,
            settings.server_certificate_json,
            "server certificate",
        )
        if certificate is not None:
            document = certificate.get("document", {})
            if (
                document.get("key_id") != settings.server_key_id
                or document.get("public_key_hex") != public_key.hex()
                or document.get("algorithm") != "Ed25519"
                or document.get("purpose") != "server_signing"
            ):
                raise ValueError("server certificate does not match operational key")
        revocation_list = load_json_document(
            settings.server_revocation_list_path,
            settings.server_revocation_list_json,
            "server revocation list",
        )
        if revocation_list is not None:
            document = revocation_list.get("document", {})
            if (
                document.get("schema_version") != "0.1.0"
                or not isinstance(document.get("issuer_key_id"), str)
                or not isinstance(document.get("revoked_keys"), list)
            ):
                raise ValueError("invalid server key revocation list")
        if certificate is not None:
            validate_certificate_time(certificate, now or datetime.now(UTC))
        root_public = load_json_document(
            settings.server_root_public_path,
            settings.server_root_public_json,
            "offline root public key",
        )
        if root_public is not None:
            if certificate is None or revocation_list is None:
                raise ValueError("root trust requires a certificate and revocation list")
            validate_root_signed_trust(
                settings,
                certificate,
                revocation_list,
                root_public,
                now or datetime.now(UTC),
            )
        return cls(
            settings.server_key_id,
            seed,
            public_key,
            certificate,
            revocation_list,
        )

    def sign(self, domain: bytes, value: object) -> str:
        return sign_canonical(domain, value, self.private_seed).hex()


def load_private_seed(path: Path) -> bytes:
    metadata = path.stat()
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError("server signing seed path must be a regular file")
    if metadata.st_mode & 0o077:
        raise ValueError("server signing seed file must not be accessible by group or others")
    try:
        seed = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError("invalid server signing seed file") from error
    if len(seed) != 32:
        raise ValueError("server signing seed must contain exactly 32 bytes")
    return seed


def server_seed_encryption_context(server_key_id: str) -> dict[str, str]:
    return {
        "application": "chitaozinho",
        "purpose": "server-signing-seed",
        "server_key_id": server_key_id,
    }


def load_json_document(
    path: Path | None,
    inline: str | None,
    label: str,
) -> dict | None:
    if path is None and inline is None:
        return None
    try:
        if inline is not None:
            raw = inline
        else:
            assert path is not None
            raw = path.read_text()
        document = json.loads(raw)
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label} JSON") from error
    if not isinstance(document, dict):
        raise ValueError(f"invalid {label} JSON")
    return document


def parse_rfc3339(value: object, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an RFC 3339 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an RFC 3339 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(UTC)


def validate_certificate_time(certificate: dict, now: datetime) -> None:
    document = certificate.get("document", {})
    valid_from = parse_rfc3339(document.get("valid_from"), "certificate valid_from")
    valid_until = parse_rfc3339(document.get("valid_until"), "certificate valid_until")
    if valid_until <= valid_from:
        raise ValueError("server certificate validity interval is empty")
    if valid_until - valid_from > timedelta(days=90):
        raise ValueError("server certificate validity exceeds 90 days")
    current = now.astimezone(UTC)
    if current < valid_from or current > valid_until:
        raise ValueError("server certificate is outside its validity interval")


def validate_root_signed_trust(
    settings: Settings,
    certificate: dict,
    revocation_list: dict,
    root: dict,
    now: datetime,
) -> None:
    if (
        root.get("schema_version") != "0.1.0"
        or root.get("algorithm") != "Ed25519"
        or not isinstance(root.get("key_id"), str)
        or not isinstance(root.get("public_key_hex"), str)
    ):
        raise ValueError("invalid offline root public key document")
    try:
        root_public_key = bytes.fromhex(root["public_key_hex"])
    except ValueError as error:
        raise ValueError("invalid offline root public key encoding") from error
    if len(root_public_key) != 32:
        raise ValueError("offline root public key must contain 32 bytes")

    certificate_document = certificate.get("document", {})
    revocation_document = revocation_list.get("document", {})
    root_key_id = root["key_id"]
    if (
        certificate_document.get("issuer_key_id") != root_key_id
        or revocation_document.get("issuer_key_id") != root_key_id
    ):
        raise ValueError("server trust documents use an unexpected root key")
    if not verify_document_signature(
        DOMAINS["key_certificate"],
        certificate,
        root_public_key,
    ):
        raise ValueError("invalid root signature on server certificate")
    if not verify_document_signature(
        DOMAINS["key_revocation_list"],
        revocation_list,
        root_public_key,
    ):
        raise ValueError("invalid root signature on server revocation list")

    issued_at = parse_rfc3339(
        revocation_document.get("issued_at"),
        "revocation list issued_at",
    )
    current = now.astimezone(UTC)
    if issued_at > current:
        raise ValueError("server revocation list is issued in the future")
    sequence = revocation_document.get("sequence")
    if not isinstance(sequence, int) or sequence < 0:
        raise ValueError("invalid server revocation list sequence")
    for revoked in revocation_document.get("revoked_keys", []):
        if not isinstance(revoked, dict):
            raise ValueError("invalid revoked key record")
        revoked_at = parse_rfc3339(revoked.get("revoked_at"), "key revoked_at")
        if revoked.get("key_id") == settings.server_key_id and revoked_at <= current:
            raise ValueError("configured server signing key is revoked")


def verify_document_signature(
    domain: bytes,
    signed_document: dict,
    root_public_key: bytes,
) -> bool:
    document = signed_document.get("document")
    signature_hex = signed_document.get("signature_hex")
    if not isinstance(document, dict) or not isinstance(signature_hex, str):
        return False
    try:
        signature = bytes.fromhex(signature_hex)
    except ValueError:
        return False
    return verify_canonical(domain, document, signature, root_public_key)
