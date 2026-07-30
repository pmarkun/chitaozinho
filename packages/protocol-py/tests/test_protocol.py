from __future__ import annotations

import json
from pathlib import Path

import pytest
from chitaozinho_protocol import (
    DOMAINS,
    base64url_decode,
    base64url_encode,
    canonical_bytes,
    sha256_identifier,
    sign_canonical,
    verify_canonical,
)

VECTOR_PATH = Path(__file__).parents[3] / "test-vectors" / "protocol-v0.1.json"


def load_vector() -> dict:
    return json.loads(VECTOR_PATH.read_text())


def test_canonicalization_and_hash() -> None:
    vector = load_vector()
    canonical = canonical_bytes(vector["entry"])
    assert canonical.decode() == vector["canonical_json"]
    assert sha256_identifier(canonical) == vector["sha256"]


def test_ed25519_signature() -> None:
    vector = load_vector()
    signature = sign_canonical(
        DOMAINS["entry"],
        vector["entry"],
        bytes.fromhex(vector["private_seed_hex"]),
    )
    assert signature.hex() == vector["signature_hex"]
    assert verify_canonical(
        DOMAINS["entry"],
        vector["entry"],
        signature,
        bytes.fromhex(vector["public_key_hex"]),
    )


def test_rejects_altered_content_domain_and_signature() -> None:
    vector = load_vector()
    signature = bytes.fromhex(vector["signature_hex"])
    public_key = bytes.fromhex(vector["public_key_hex"])
    assert not verify_canonical(
        DOMAINS["entry"],
        {**vector["entry"], "sequence": 2},
        signature,
        public_key,
    )
    assert not verify_canonical(
        DOMAINS["receipt"],
        vector["entry"],
        signature,
        public_key,
    )
    altered_signature = bytes([signature[0] ^ 1, *signature[1:]])
    assert not verify_canonical(
        DOMAINS["entry"],
        vector["entry"],
        altered_signature,
        public_key,
    )


def test_base64url_has_no_padding() -> None:
    vector = load_vector()["base64url"]
    value = bytes.fromhex(vector["bytes_hex"])
    assert base64url_encode(value) == vector["encoded"]
    assert base64url_decode(vector["encoded"]) == value
    with pytest.raises(ValueError):
        base64url_decode("AAEC-_8=")
