from __future__ import annotations

import base64
import hashlib
from typing import Any

import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

DOMAINS = {
    "entry": b"CHITAOZINHO/ENTRY/v1",
    "receipt": b"CHITAOZINHO/RECEIPT/v1",
    "capture_close": b"CHITAOZINHO/CAPTURE_CLOSE/v1",
    "manifest": b"CHITAOZINHO/MANIFEST/v1",
    "package_index": b"CHITAOZINHO/PACKAGE_INDEX/v1",
    "attestation": b"CHITAOZINHO/ATTESTATION/v1",
    "proof_bundle_index": b"CHITAOZINHO/PROOF_BUNDLE_INDEX/v1",
}


def canonical_bytes(value: Any) -> bytes:
    return rfc8785.dumps(value)


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_identifier(data: bytes) -> str:
    return f"sha256:{sha256_bytes(data).hex()}"


def base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def base64url_decode(value: str) -> bytes:
    if "=" in value:
        raise ValueError("Base64URL padding is not allowed")
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def hash_canonical(value: Any) -> bytes:
    return sha256_bytes(canonical_bytes(value))


def sign_canonical(domain: bytes, value: Any, private_seed: bytes) -> bytes:
    if len(private_seed) != 32:
        raise ValueError("Ed25519 private seed must contain 32 bytes")
    key = Ed25519PrivateKey.from_private_bytes(private_seed)
    return key.sign(domain + hash_canonical(value))


def verify_canonical(
    domain: bytes,
    value: Any,
    signature: bytes,
    public_key: bytes,
) -> bool:
    if len(public_key) != 32:
        raise ValueError("Ed25519 public key must contain 32 bytes")
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            domain + hash_canonical(value),
        )
    except InvalidSignature:
        return False
    return True


__all__ = [
    "DOMAINS",
    "base64url_decode",
    "base64url_encode",
    "canonical_bytes",
    "hash_canonical",
    "sha256_bytes",
    "sha256_identifier",
    "sign_canonical",
    "verify_canonical",
]
