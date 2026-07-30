from __future__ import annotations

import argparse
import json
import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from chitaozinho_protocol import DOMAINS, canonical_bytes, sign_canonical
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def issue_operational_certificate(
    *,
    root_seed: bytes,
    root_key_id: str,
    operational_public_key: bytes,
    operational_key_id: str,
    valid_from: datetime,
    valid_until: datetime,
) -> dict:
    if len(root_seed) != 32 or len(operational_public_key) != 32:
        raise ValueError("Ed25519 keys must contain 32 bytes")
    if valid_from.tzinfo is None or valid_until.tzinfo is None:
        raise ValueError("certificate validity requires timezone-aware values")
    if valid_until <= valid_from:
        raise ValueError("certificate validity interval is empty")
    document = {
        "schema_version": "0.1.0",
        "key_id": operational_key_id,
        "algorithm": "Ed25519",
        "public_key_hex": operational_public_key.hex(),
        "purpose": "server_signing",
        "issuer_key_id": root_key_id,
        "valid_from": rfc3339(valid_from),
        "valid_until": rfc3339(valid_until),
    }
    return {
        "document": document,
        "signature_hex": sign_canonical(
            DOMAINS["key_certificate"],
            document,
            root_seed,
        ).hex(),
    }


def issue_revocation_list(
    *,
    root_seed: bytes,
    root_key_id: str,
    sequence: int,
    issued_at: datetime,
    revoked_keys: list[dict],
) -> dict:
    if len(root_seed) != 32:
        raise ValueError("Ed25519 root seed must contain 32 bytes")
    if sequence < 0:
        raise ValueError("revocation list sequence cannot be negative")
    if issued_at.tzinfo is None:
        raise ValueError("revocation list issue time requires a timezone")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for revoked in revoked_keys:
        key_id = revoked.get("key_id")
        reason = revoked.get("reason")
        revoked_at_value = revoked.get("revoked_at")
        if (
            not isinstance(key_id, str)
            or not key_id
            or not isinstance(reason, str)
            or not reason
            or not isinstance(revoked_at_value, str)
        ):
            raise ValueError("invalid revoked key record")
        if key_id in seen:
            raise ValueError(f"duplicate revoked key: {key_id}")
        revoked_at = datetime.fromisoformat(revoked_at_value.replace("Z", "+00:00"))
        if revoked_at.tzinfo is None or revoked_at > issued_at:
            raise ValueError("revocation time must not be after list issue time")
        seen.add(key_id)
        normalized.append(
            {
                "key_id": key_id,
                "revoked_at": rfc3339(revoked_at),
                "reason": reason,
            }
        )
    document = {
        "schema_version": "0.1.0",
        "issuer_key_id": root_key_id,
        "sequence": sequence,
        "issued_at": rfc3339(issued_at),
        "revoked_keys": sorted(normalized, key=lambda value: value["key_id"]),
    }
    return {
        "document": document,
        "signature_hex": sign_canonical(
            DOMAINS["key_revocation_list"],
            document,
            root_seed,
        ).hex(),
    }


def public_key_from_seed(seed: bytes) -> bytes:
    return (
        Ed25519PrivateKey.from_private_bytes(seed)
        .public_key()
        .public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    )


def rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def write_new(path: Path, content: bytes, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Chitãozinho key tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    root_parser = subparsers.add_parser("generate-root")
    root_parser.add_argument("--output-dir", type=Path, required=True)
    root_parser.add_argument("--key-id", required=True)
    issue_parser = subparsers.add_parser("issue-operational")
    issue_parser.add_argument("--root-seed-file", type=Path, required=True)
    issue_parser.add_argument("--root-key-id", required=True)
    issue_parser.add_argument("--operational-key-id", required=True)
    issue_parser.add_argument("--operational-public-key-hex", required=True)
    issue_parser.add_argument("--valid-from", required=True)
    issue_parser.add_argument("--valid-until", required=True)
    issue_parser.add_argument("--output", type=Path, required=True)
    revocation_parser = subparsers.add_parser("issue-revocations")
    revocation_parser.add_argument("--root-seed-file", type=Path, required=True)
    revocation_parser.add_argument("--root-key-id", required=True)
    revocation_parser.add_argument("--sequence", type=int, required=True)
    revocation_parser.add_argument("--issued-at", required=True)
    revocation_parser.add_argument("--revocations-file", type=Path, required=True)
    revocation_parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "generate-root":
        seed = secrets.token_bytes(32)
        write_new(arguments.output_dir / "root.seed", seed.hex().encode() + b"\n", 0o600)
        public_document = {
            "schema_version": "0.1.0",
            "key_id": arguments.key_id,
            "algorithm": "Ed25519",
            "public_key_hex": public_key_from_seed(seed).hex(),
            "created_at": rfc3339(datetime.now(UTC)),
        }
        write_new(
            arguments.output_dir / "root-public.json",
            canonical_bytes(public_document) + b"\n",
            0o644,
        )
        return
    root_seed = bytes.fromhex(arguments.root_seed_file.read_text().strip())
    if arguments.command == "issue-operational":
        result = issue_operational_certificate(
            root_seed=root_seed,
            root_key_id=arguments.root_key_id,
            operational_public_key=bytes.fromhex(arguments.operational_public_key_hex),
            operational_key_id=arguments.operational_key_id,
            valid_from=datetime.fromisoformat(arguments.valid_from.replace("Z", "+00:00")),
            valid_until=datetime.fromisoformat(arguments.valid_until.replace("Z", "+00:00")),
        )
    else:
        revoked_keys = json.loads(arguments.revocations_file.read_text())
        if not isinstance(revoked_keys, list):
            raise ValueError("revocations file must contain a JSON array")
        result = issue_revocation_list(
            root_seed=root_seed,
            root_key_id=arguments.root_key_id,
            sequence=arguments.sequence,
            issued_at=datetime.fromisoformat(arguments.issued_at.replace("Z", "+00:00")),
            revoked_keys=revoked_keys,
        )
    write_new(
        arguments.output,
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode() + b"\n",
        0o644,
    )


if __name__ == "__main__":
    main()
