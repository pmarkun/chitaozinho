from __future__ import annotations

import json
from dataclasses import dataclass

from chitaozinho_protocol import sign_canonical
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .config import Settings


@dataclass(frozen=True)
class ServerSigner:
    key_id: str
    private_seed: bytes
    public_key: bytes
    certificate: dict | None
    revocation_list: dict | None

    @classmethod
    def from_settings(cls, settings: Settings) -> ServerSigner | None:
        if settings.server_seed_hex is None:
            return None
        seed = bytes.fromhex(settings.server_seed_hex)
        private_key = Ed25519PrivateKey.from_private_bytes(seed)
        public_key = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        certificate = (
            json.loads(settings.server_certificate_path.read_text())
            if settings.server_certificate_path is not None
            else None
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
        revocation_list = (
            json.loads(settings.server_revocation_list_path.read_text())
            if settings.server_revocation_list_path is not None
            else None
        )
        if revocation_list is not None:
            document = revocation_list.get("document", {})
            if (
                document.get("schema_version") != "0.1.0"
                or not isinstance(document.get("issuer_key_id"), str)
                or not isinstance(document.get("revoked_keys"), list)
            ):
                raise ValueError("invalid server key revocation list")
        return cls(
            settings.server_key_id,
            seed,
            public_key,
            certificate,
            revocation_list,
        )

    def sign(self, domain: bytes, value: object) -> str:
        return sign_canonical(domain, value, self.private_seed).hex()
