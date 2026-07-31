from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import boto3
from chitaozinho_protocol import DOMAINS, canonical_bytes, sign_canonical
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .security import server_seed_encryption_context


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
    if valid_until - valid_from > timedelta(days=90):
        raise ValueError("certificate validity cannot exceed 90 days")
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


def require_new_paths(*paths: Path) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise FileExistsError(f"refusing to overwrite: {', '.join(existing)}")


def encrypt_operational_seed(
    *,
    seed: bytes,
    kms_client: Any,
    kms_key_id: str,
    operational_key_id: str,
) -> bytes:
    if len(seed) != 32:
        raise ValueError("Ed25519 operational seed must contain 32 bytes")
    response = kms_client.encrypt(
        KeyId=kms_key_id,
        Plaintext=seed,
        EncryptionAlgorithm="SYMMETRIC_DEFAULT",
        EncryptionContext=server_seed_encryption_context(operational_key_id),
    )
    if response.get("KeyId") != kms_key_id:
        raise ValueError("KMS encrypted operational seed with an unexpected key")
    ciphertext = response.get("CiphertextBlob")
    if not isinstance(ciphertext, bytes) or not ciphertext:
        raise ValueError("KMS did not return operational seed ciphertext")
    return ciphertext


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline Chitãozinho key tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)
    root_parser = subparsers.add_parser("generate-root")
    root_parser.add_argument("--output-dir", type=Path, required=True)
    root_parser.add_argument("--key-id", required=True)
    mounted_parser = subparsers.add_parser("generate-operational-file")
    mounted_parser.add_argument("--output-dir", type=Path, required=True)
    mounted_parser.add_argument("--operational-key-id", required=True)
    operational_parser = subparsers.add_parser("generate-operational-envelope")
    operational_parser.add_argument("--output-dir", type=Path, required=True)
    operational_parser.add_argument("--operational-key-id", required=True)
    operational_parser.add_argument("--kms-key-arn", required=True)
    operational_parser.add_argument("--region", default="sa-east-1")
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
    encrypt_parser = subparsers.add_parser("encrypt-operational")
    encrypt_parser.add_argument("--seed-file", type=Path, required=True)
    encrypt_parser.add_argument("--kms-key-arn", required=True)
    encrypt_parser.add_argument("--operational-key-id", required=True)
    encrypt_parser.add_argument("--region", default="sa-east-1")
    encrypt_parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.command == "generate-root":
        root_seed_path = arguments.output_dir / "root.seed"
        root_public_path = arguments.output_dir / "root-public.json"
        require_new_paths(root_seed_path, root_public_path)
        seed = secrets.token_bytes(32)
        write_new(root_seed_path, seed.hex().encode() + b"\n", 0o600)
        public_document = {
            "schema_version": "0.1.0",
            "key_id": arguments.key_id,
            "algorithm": "Ed25519",
            "public_key_hex": public_key_from_seed(seed).hex(),
            "created_at": rfc3339(datetime.now(UTC)),
        }
        write_new(
            root_public_path,
            canonical_bytes(public_document) + b"\n",
            0o644,
        )
        return
    if arguments.command == "generate-operational-file":
        seed_path = arguments.output_dir / f"{arguments.operational_key_id}.seed"
        public_path = arguments.output_dir / f"{arguments.operational_key_id}.public.json"
        require_new_paths(seed_path, public_path)
        seed_buffer = bytearray(secrets.token_bytes(32))
        try:
            write_new(seed_path, bytes(seed_buffer).hex().encode() + b"\n", 0o600)
            public_document = {
                "schema_version": "0.1.0",
                "key_id": arguments.operational_key_id,
                "algorithm": "Ed25519",
                "public_key_hex": public_key_from_seed(bytes(seed_buffer)).hex(),
                "created_at": rfc3339(datetime.now(UTC)),
                "seed_protection": {"method": "runtime-secret-mount"},
            }
            write_new(
                public_path,
                canonical_bytes(public_document) + b"\n",
                0o644,
            )
        finally:
            seed_buffer[:] = b"\0" * len(seed_buffer)
        return
    if arguments.command == "generate-operational-envelope":
        ciphertext_path = arguments.output_dir / f"{arguments.operational_key_id}.seed.kms.b64"
        public_path = arguments.output_dir / f"{arguments.operational_key_id}.public.json"
        require_new_paths(ciphertext_path, public_path)
        seed_buffer = bytearray(secrets.token_bytes(32))
        try:
            ciphertext = encrypt_operational_seed(
                seed=bytes(seed_buffer),
                kms_client=boto3.client("kms", region_name=arguments.region),
                kms_key_id=arguments.kms_key_arn,
                operational_key_id=arguments.operational_key_id,
            )
            write_new(
                ciphertext_path,
                base64.b64encode(ciphertext) + b"\n",
                0o600,
            )
            public_document = {
                "schema_version": "0.1.0",
                "key_id": arguments.operational_key_id,
                "algorithm": "Ed25519",
                "public_key_hex": public_key_from_seed(bytes(seed_buffer)).hex(),
                "created_at": rfc3339(datetime.now(UTC)),
                "seed_protection": {
                    "method": "aws-kms-symmetric-encryption",
                    "kms_key_arn": arguments.kms_key_arn,
                    "encryption_context": server_seed_encryption_context(
                        arguments.operational_key_id
                    ),
                },
            }
            write_new(
                public_path,
                canonical_bytes(public_document) + b"\n",
                0o644,
            )
        finally:
            seed_buffer[:] = b"\0" * len(seed_buffer)
        return
    if arguments.command == "encrypt-operational":
        seed_buffer = bytearray.fromhex(arguments.seed_file.read_text().strip())
        try:
            ciphertext = encrypt_operational_seed(
                seed=bytes(seed_buffer),
                kms_client=boto3.client("kms", region_name=arguments.region),
                kms_key_id=arguments.kms_key_arn,
                operational_key_id=arguments.operational_key_id,
            )
            write_new(
                arguments.output,
                base64.b64encode(ciphertext) + b"\n",
                0o600,
            )
        finally:
            seed_buffer[:] = b"\0" * len(seed_buffer)
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
