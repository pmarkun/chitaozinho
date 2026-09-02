from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.key_management import (
    issue_operational_certificate,
    issue_revocation_list,
    public_key_from_seed,
)
from chitaozinho_api.security import OpenBaoTransitClient, ServerSigner
from chitaozinho_protocol import DOMAINS, verify_canonical
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_DIR = Path(__file__).parents[3] / "packages" / "schemas"


class BaoResponse:
    def __init__(self, document: dict) -> None:
        self.document = document

    def __enter__(self):
        return self

    def __exit__(self, *_arguments) -> None:
        return None

    def read(self, _limit: int) -> bytes:
        return json.dumps(self.document).encode()


class BaoOpener:
    def __init__(self) -> None:
        self.paths: list[str] = []

    def open(self, request, *, timeout: float):
        assert timeout == 5
        self.paths.append(request.full_url)
        if request.full_url.endswith("/auth/approle/login"):
            return BaoResponse(
                {
                    "auth": {
                        "client_token": "leased-token",
                        "lease_duration": 3600,
                        "renewable": True,
                    }
                }
            )
        if request.full_url.endswith("/auth/token/renew-self"):
            return BaoResponse(
                {
                    "auth": {
                        "client_token": "renewed-token",
                        "lease_duration": 3600,
                        "renewable": True,
                    }
                }
            )
        return BaoResponse({"data": {"keys": {}}})


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


def test_server_signer_reads_private_mounted_seed(tmp_path: Path) -> None:
    seed = bytes([53]) * 32
    seed_path = tmp_path / "server.seed"
    seed_path.write_text(seed.hex() + "\n")
    seed_path.chmod(0o600)

    signer = ServerSigner.from_settings(
        Settings(
            _env_file=None,
            server_key_id="server-file-test",
            server_seed_path=seed_path,
        )
    )

    assert signer is not None
    assert signer.public_key == public_key_from_seed(seed)

    seed_path.chmod(0o640)
    with pytest.raises(ValueError, match="group or others"):
        ServerSigner.from_settings(
            Settings(
                _env_file=None,
                server_key_id="server-file-test",
                server_seed_path=seed_path,
            )
        )


def test_openbao_approle_login_and_lease_renewal() -> None:
    opener = BaoOpener()
    with patch("chitaozinho_api.security.build_opener", return_value=opener):
        client = OpenBaoTransitClient(
            "https://openbao.example.test",
            None,
            None,
            role_id="role-id",
            secret_id="secret-id",
        )
        client.read_key("transit", "signing")
        client.token_expires_at = datetime.now(UTC)
        client.read_key("transit", "signing")

    assert sum(path.endswith("/auth/approle/login") for path in opener.paths) == 1
    assert sum(path.endswith("/auth/token/renew-self") for path in opener.paths) == 1
    assert opener.paths[-1].endswith("/transit/keys/signing")


def test_server_signer_uses_pinned_openbao_transit_key() -> None:
    seed = bytes([54]) * 32
    transit = FakeTransitClient(seed, key_version=3)
    signer = ServerSigner.from_settings(
        Settings(
            _env_file=None,
            server_key_id="server-openbao-test",
            openbao_addr="https://openbao.example.test",
            openbao_token="synthetic-openbao-token",
            openbao_transit_key="chitaozinho-server",
            openbao_transit_key_version=3,
        ),
        transit_client=transit,
    )
    assert signer is not None

    document = {"synthetic": True}
    signature = bytes.fromhex(signer.sign(DOMAINS["receipt"], document))

    assert verify_canonical(
        DOMAINS["receipt"],
        document,
        signature,
        public_key_from_seed(seed),
    )
    assert transit.read_arguments == ("transit", "chitaozinho-server")
    assert transit.sign_arguments[:3] == (
        "transit",
        "chitaozinho-server",
        3,
    )
    assert "synthetic-openbao-token" not in repr(signer)
    signer.check_ready()

    transit.response_version = 4
    with pytest.raises(RuntimeError, match="unexpected signing key version"):
        signer.sign(DOMAINS["receipt"], document)

    transit.public_key = public_key_from_seed(bytes([55]) * 32)
    with pytest.raises(RuntimeError, match="does not match the active key"):
        signer.check_ready()


class FakeTransitClient:
    def __init__(self, seed: bytes, key_version: int) -> None:
        self.private_key = Ed25519PrivateKey.from_private_bytes(seed)
        self.public_key = public_key_from_seed(seed)
        self.key_version = key_version
        self.response_version = key_version
        self.read_arguments: tuple[str, str] | None = None
        self.sign_arguments: tuple[str, str, int, str] | None = None

    def read_key(self, mount: str, key: str) -> dict:
        self.read_arguments = (mount, key)
        return {
            "data": {
                "type": "ed25519",
                "supports_signing": True,
                "derived": False,
                "keys": {
                    str(self.key_version): {
                        "public_key": base64.b64encode(self.public_key).decode()
                    }
                },
            }
        }

    def sign(
        self,
        mount: str,
        key: str,
        key_version: int,
        encoded_input: str,
    ) -> dict:
        self.sign_arguments = (mount, key, key_version, encoded_input)
        message = base64.b64decode(encoded_input, validate=True)
        signature = self.private_key.sign(message)
        return {
            "data": {
                "signature": (
                    f"vault:v{self.response_version}:" + base64.b64encode(signature).decode()
                )
            }
        }
