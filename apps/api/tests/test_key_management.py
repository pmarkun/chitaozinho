from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.key_management import (
    encrypt_operational_seed,
    issue_operational_certificate,
    issue_revocation_list,
    public_key_from_seed,
)
from chitaozinho_api.security import ServerSigner, server_seed_encryption_context
from chitaozinho_protocol import DOMAINS, verify_canonical
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).parents[3] / "packages" / "schemas"


def test_root_signs_operational_key_certificate(tmp_path: Path) -> None:
    root_seed = bytes([31]) * 32
    operational_seed = bytes([32]) * 32
    valid_from = datetime.now(UTC).replace(microsecond=0)
    certificate = issue_operational_certificate(
        root_seed=root_seed,
        root_key_id="root-test",
        operational_public_key=public_key_from_seed(operational_seed),
        operational_key_id="server-test",
        valid_from=valid_from,
        valid_until=valid_from + timedelta(days=90),
    )
    Draft202012Validator(
        json.loads((SCHEMA_DIR / "key-certificate.schema.json").read_text()),
        format_checker=FormatChecker(),
    ).validate(certificate)
    assert verify_canonical(
        DOMAINS["key_certificate"],
        certificate["document"],
        bytes.fromhex(certificate["signature_hex"]),
        public_key_from_seed(root_seed),
    )

    certificate_path = tmp_path / "server-certificate.json"
    certificate_path.write_text(json.dumps(certificate))
    revocation_list = issue_revocation_list(
        root_seed=root_seed,
        root_key_id="root-test",
        sequence=0,
        issued_at=valid_from,
        revoked_keys=[],
    )
    revocation_path = tmp_path / "key-revocations.json"
    revocation_path.write_text(json.dumps(revocation_list))
    root_public_path = tmp_path / "root-public.json"
    root_public_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "key_id": "root-test",
                "algorithm": "Ed25519",
                "public_key_hex": public_key_from_seed(root_seed).hex(),
                "created_at": valid_from.isoformat(),
            }
        )
    )
    signer = ServerSigner.from_settings(
        Settings(
            server_key_id="server-test",
            server_seed_hex=operational_seed.hex(),
            server_certificate_path=certificate_path,
            server_revocation_list_path=revocation_path,
            server_root_public_path=root_public_path,
        )
    )
    assert signer is not None
    assert signer.certificate == certificate
    assert signer.revocation_list == revocation_list

    inline_signer = ServerSigner.from_settings(
        Settings(
            server_key_id="server-test",
            server_seed_hex=operational_seed.hex(),
            server_certificate_json=json.dumps(certificate),
            server_revocation_list_json=json.dumps(revocation_list),
            server_root_public_json=root_public_path.read_text(),
        )
    )
    assert inline_signer is not None
    assert inline_signer.public_key == signer.public_key

    with pytest.raises(ValueError, match="does not match"):
        ServerSigner.from_settings(
            Settings(
                server_key_id="different-key",
                server_seed_hex=operational_seed.hex(),
                server_certificate_path=certificate_path,
            )
        )


def test_root_signs_canonical_key_revocation_history() -> None:
    root_seed = bytes([41]) * 32
    issued_at = datetime.now(UTC).replace(microsecond=0)
    revocations = issue_revocation_list(
        root_seed=root_seed,
        root_key_id="root-test",
        sequence=3,
        issued_at=issued_at,
        revoked_keys=[
            {
                "key_id": "server-old",
                "revoked_at": (issued_at - timedelta(hours=1)).isoformat(),
                "reason": "scheduled rotation",
            }
        ],
    )
    Draft202012Validator(
        json.loads((SCHEMA_DIR / "key-revocation-list.schema.json").read_text()),
        format_checker=FormatChecker(),
    ).validate(revocations)
    assert verify_canonical(
        DOMAINS["key_revocation_list"],
        revocations["document"],
        bytes.fromhex(revocations["signature_hex"]),
        public_key_from_seed(root_seed),
    )
    assert revocations["document"]["sequence"] == 3

    with pytest.raises(ValueError, match="duplicate revoked key"):
        issue_revocation_list(
            root_seed=root_seed,
            root_key_id="root-test",
            sequence=4,
            issued_at=issued_at,
            revoked_keys=[
                {
                    "key_id": "duplicate",
                    "revoked_at": issued_at.isoformat(),
                    "reason": "first",
                },
                {
                    "key_id": "duplicate",
                    "revoked_at": issued_at.isoformat(),
                    "reason": "second",
                },
            ],
        )


def test_server_refuses_expired_long_lived_revoked_and_tampered_keys(
    tmp_path: Path,
) -> None:
    root_seed = bytes([71]) * 32
    operational_seed = bytes([72]) * 32
    now = datetime.now(UTC).replace(microsecond=0)

    with pytest.raises(ValueError, match="cannot exceed 90 days"):
        issue_operational_certificate(
            root_seed=root_seed,
            root_key_id="root-test",
            operational_public_key=public_key_from_seed(operational_seed),
            operational_key_id="server-test",
            valid_from=now,
            valid_until=now + timedelta(days=91),
        )

    certificate = issue_operational_certificate(
        root_seed=root_seed,
        root_key_id="root-test",
        operational_public_key=public_key_from_seed(operational_seed),
        operational_key_id="server-test",
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=89),
    )
    revocations = issue_revocation_list(
        root_seed=root_seed,
        root_key_id="root-test",
        sequence=1,
        issued_at=now,
        revoked_keys=[
            {
                "key_id": "server-test",
                "revoked_at": (now - timedelta(minutes=1)).isoformat(),
                "reason": "synthetic compromise",
            }
        ],
    )
    certificate_path = tmp_path / "certificate.json"
    revocation_path = tmp_path / "revocations.json"
    root_path = tmp_path / "root-public.json"
    certificate_path.write_text(json.dumps(certificate))
    revocation_path.write_text(json.dumps(revocations))
    root_path.write_text(
        json.dumps(
            {
                "schema_version": "0.1.0",
                "key_id": "root-test",
                "algorithm": "Ed25519",
                "public_key_hex": public_key_from_seed(root_seed).hex(),
            }
        )
    )
    settings = Settings(
        server_key_id="server-test",
        server_seed_hex=operational_seed.hex(),
        server_certificate_path=certificate_path,
        server_revocation_list_path=revocation_path,
        server_root_public_path=root_path,
    )

    with pytest.raises(ValueError, match="is revoked"):
        ServerSigner.from_settings(settings, now=now)

    clean_revocations = issue_revocation_list(
        root_seed=root_seed,
        root_key_id="root-test",
        sequence=2,
        issued_at=now,
        revoked_keys=[],
    )
    revocation_path.write_text(json.dumps(clean_revocations))
    tampered = dict(certificate)
    tampered["signature_hex"] = "00" * 64
    certificate_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="invalid root signature"):
        ServerSigner.from_settings(settings, now=now)

    certificate_path.write_text(json.dumps(certificate))
    with pytest.raises(ValueError, match="outside its validity"):
        ServerSigner.from_settings(settings, now=now + timedelta(days=90))


def test_server_signer_decrypts_kms_envelope_with_bound_context() -> None:
    seed = bytes([51]) * 32
    ciphertext = b"synthetic-kms-ciphertext"
    kms_key_id = "arn:aws:kms:sa-east-1:123456789012:key/signing-envelope"
    kms = FakeKmsClient(seed, kms_key_id)
    settings = Settings(
        server_key_id="server-kms-test",
        server_seed_kms_ciphertext_b64=base64.b64encode(ciphertext).decode(),
        server_seed_kms_key_id=kms_key_id,
    )

    signer = ServerSigner.from_settings(settings, kms_client=kms)

    assert signer is not None
    assert signer.public_key == public_key_from_seed(seed)
    assert seed.hex() not in repr(signer)
    assert kms.decrypt_arguments == {
        "CiphertextBlob": ciphertext,
        "KeyId": kms_key_id,
        "EncryptionAlgorithm": "SYMMETRIC_DEFAULT",
        "EncryptionContext": server_seed_encryption_context("server-kms-test"),
    }


def test_server_signer_reads_private_mounted_seed(tmp_path: Path) -> None:
    seed = bytes([53]) * 32
    seed_path = tmp_path / "server.seed"
    seed_path.write_text(seed.hex() + "\n")
    seed_path.chmod(0o600)

    signer = ServerSigner.from_settings(
        Settings(server_key_id="server-file-test", server_seed_path=seed_path)
    )

    assert signer is not None
    assert signer.public_key == public_key_from_seed(seed)

    seed_path.chmod(0o640)
    with pytest.raises(ValueError, match="group or others"):
        ServerSigner.from_settings(
            Settings(server_key_id="server-file-test", server_seed_path=seed_path)
        )


def test_server_signer_rejects_invalid_kms_results() -> None:
    kms_key_id = "arn:aws:kms:sa-east-1:123456789012:key/signing-envelope"
    settings = Settings(
        server_key_id="server-kms-test",
        server_seed_kms_ciphertext_b64=base64.b64encode(b"ciphertext").decode(),
        server_seed_kms_key_id=kms_key_id,
    )

    with pytest.raises(ValueError, match="unexpected key"):
        ServerSigner.from_settings(
            settings,
            kms_client=FakeKmsClient(bytes([52]) * 32, "different-key"),
        )
    with pytest.raises(ValueError, match="exactly 32 bytes"):
        ServerSigner.from_settings(
            settings,
            kms_client=FakeKmsClient(b"short", kms_key_id),
        )


class FakeKmsClient:
    def __init__(self, plaintext: bytes, key_id: str) -> None:
        self.plaintext = plaintext
        self.key_id = key_id
        self.decrypt_arguments: dict = {}

    def decrypt(self, **arguments) -> dict:
        self.decrypt_arguments = arguments
        return {"Plaintext": self.plaintext, "KeyId": self.key_id}


class FakeKmsEncryptClient:
    def __init__(self, ciphertext: bytes, key_id: str) -> None:
        self.ciphertext = ciphertext
        self.key_id = key_id
        self.encrypt_arguments: dict = {}

    def encrypt(self, **arguments) -> dict:
        self.encrypt_arguments = arguments
        return {"CiphertextBlob": self.ciphertext, "KeyId": self.key_id}


def test_operational_seed_encryption_uses_same_bound_context() -> None:
    seed = bytes([61]) * 32
    kms_key_id = "arn:aws:kms:sa-east-1:123456789012:key/signing-envelope"
    kms = FakeKmsEncryptClient(b"kms-ciphertext", kms_key_id)

    ciphertext = encrypt_operational_seed(
        seed=seed,
        kms_client=kms,
        kms_key_id=kms_key_id,
        operational_key_id="server-rotation-1",
    )

    assert ciphertext == b"kms-ciphertext"
    assert kms.encrypt_arguments == {
        "KeyId": kms_key_id,
        "Plaintext": seed,
        "EncryptionAlgorithm": "SYMMETRIC_DEFAULT",
        "EncryptionContext": server_seed_encryption_context("server-rotation-1"),
    }
