from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from chitaozinho_api.config import Settings
from chitaozinho_api.key_management import (
    issue_operational_certificate,
    issue_revocation_list,
    public_key_from_seed,
)
from chitaozinho_api.security import ServerSigner
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
    signer = ServerSigner.from_settings(
        Settings(
            server_key_id="server-test",
            server_seed_hex=operational_seed.hex(),
            server_certificate_path=certificate_path,
            server_revocation_list_path=revocation_path,
        )
    )
    assert signer is not None
    assert signer.certificate == certificate
    assert signer.revocation_list == revocation_list

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
