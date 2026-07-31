from __future__ import annotations

import base64
import json
import ssl
import stat
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import (
    HTTPRedirectHandler,
    HTTPSHandler,
    Request,
    build_opener,
)

from chitaozinho_protocol import (
    DOMAINS,
    hash_canonical,
    sign_canonical,
    verify_canonical,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import Settings


@dataclass(frozen=True)
class ServerSigner:
    key_id: str
    private_seed: bytes | None = field(repr=False)
    public_key: bytes
    certificate: dict | None
    revocation_list: dict | None
    transit_client: Any | None = field(default=None, repr=False)
    transit_mount: str | None = None
    transit_key: str | None = None
    transit_key_version: int | None = None

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        *,
        transit_client: Any | None = None,
        now: datetime | None = None,
    ) -> ServerSigner | None:
        if (
            settings.server_seed_hex is None
            and settings.server_seed_path is None
            and settings.openbao_addr is None
        ):
            return None
        active_transit_client = None
        if settings.openbao_addr is not None:
            assert settings.openbao_token is not None
            assert settings.openbao_transit_key is not None
            assert settings.openbao_transit_key_version is not None
            active_transit_client = transit_client or OpenBaoTransitClient(
                settings.openbao_addr,
                settings.openbao_token,
                settings.openbao_ca_bundle,
            )
            key_document = active_transit_client.read_key(
                settings.openbao_transit_mount,
                settings.openbao_transit_key,
            )
            public_key = load_openbao_public_key(
                key_document,
                settings.openbao_transit_key_version,
            )
            seed = None
        elif settings.server_seed_hex is not None:
            seed = bytes.fromhex(settings.server_seed_hex)
        elif settings.server_seed_path is not None:
            seed = load_private_seed(settings.server_seed_path)
        else:
            raise ValueError("server signer configuration is incomplete")
        if seed is not None:
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
            active_transit_client,
            settings.openbao_transit_mount if active_transit_client is not None else None,
            settings.openbao_transit_key if active_transit_client is not None else None,
            (settings.openbao_transit_key_version if active_transit_client is not None else None),
        )

    def sign(self, domain: bytes, value: object) -> str:
        if self.private_seed is not None:
            return sign_canonical(domain, value, self.private_seed).hex()
        if (
            self.transit_client is None
            or self.transit_mount is None
            or self.transit_key is None
            or self.transit_key_version is None
        ):
            raise RuntimeError("server signer has no signing backend")
        message = domain + hash_canonical(value)
        encoded = base64.b64encode(message).decode("ascii")
        response = self.transit_client.sign(
            self.transit_mount,
            self.transit_key,
            self.transit_key_version,
            encoded,
        )
        signature = decode_openbao_signature(response, self.transit_key_version)
        if not verify_canonical(domain, value, signature, self.public_key):
            raise RuntimeError("OpenBao returned a signature that does not match the active key")
        return signature.hex()


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


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenBaoTransitClient:
    def __init__(
        self,
        address: str,
        token: str,
        ca_bundle: Path | None,
        *,
        timeout_seconds: float = 5.0,
    ) -> None:
        self.address = address.rstrip("/")
        self.token = token
        self.timeout_seconds = timeout_seconds
        context = ssl.create_default_context(
            cafile=str(ca_bundle) if ca_bundle is not None else None
        )
        self.opener = build_opener(RejectRedirects(), HTTPSHandler(context=context))

    def read_key(self, mount: str, key: str) -> dict[str, Any]:
        return self._request("GET", f"{quote(mount)}/keys/{quote(key)}")

    def sign(
        self,
        mount: str,
        key: str,
        key_version: int,
        encoded_input: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"{quote(mount)}/sign/{quote(key)}",
            {
                "input": encoded_input,
                "key_version": key_version,
                "prehashed": False,
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode()
        request = Request(
            f"{self.address}/v1/{path}",
            data=body,
            method=method,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Vault-Token": self.token,
            },
        )
        try:
            with self.opener.open(request, timeout=self.timeout_seconds) as response:
                content = response.read(65_537)
        except HTTPError as error:
            raise RuntimeError(f"OpenBao request failed with HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError("OpenBao request failed") from error
        if len(content) > 65_536:
            raise RuntimeError("OpenBao response exceeds the safety limit")
        try:
            document = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenBao returned invalid JSON") from error
        if not isinstance(document, dict):
            raise RuntimeError("OpenBao returned an invalid response")
        return document


def load_openbao_public_key(document: dict[str, Any], key_version: int) -> bytes:
    data = document.get("data")
    if (
        not isinstance(data, dict)
        or data.get("type") != "ed25519"
        or data.get("supports_signing") is not True
        or data.get("derived") is not False
    ):
        raise ValueError("OpenBao Transit key must be a non-derived Ed25519 signing key")
    keys = data.get("keys")
    version = keys.get(str(key_version)) if isinstance(keys, dict) else None
    encoded = version.get("public_key") if isinstance(version, dict) else None
    if not isinstance(encoded, str):
        raise ValueError("OpenBao Transit key version has no public key")
    try:
        public_key = base64.b64decode(encoded, validate=True)
    except ValueError as error:
        raise ValueError("OpenBao Transit public key is not valid Base64") from error
    if len(public_key) != 32:
        raise ValueError("OpenBao Transit public key must contain exactly 32 bytes")
    return public_key


def decode_openbao_signature(document: dict[str, Any], key_version: int) -> bytes:
    data = document.get("data")
    value = data.get("signature") if isinstance(data, dict) else None
    prefix = f"vault:v{key_version}:"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise RuntimeError("OpenBao returned an unexpected signing key version")
    try:
        signature = base64.b64decode(value[len(prefix) :], validate=True)
    except ValueError as error:
        raise RuntimeError("OpenBao returned an invalid signature encoding") from error
    if len(signature) != 64:
        raise RuntimeError("OpenBao returned an invalid Ed25519 signature")
    return signature


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
