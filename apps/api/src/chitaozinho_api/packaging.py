from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from chitaozinho_protocol import DOMAINS, canonical_bytes, sha256_identifier
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import append_audit_event
from .models import Artifact, ArtifactPart, CaptureSession, ChainEntry, Receipt
from .security import ServerSigner
from .storage import DurableStorage


def ensure_package(
    database: Session,
    storage: DurableStorage,
    signer: ServerSigner,
    capture_session: CaptureSession,
) -> tuple[Path, str]:
    target = storage.package_path(capture_session.id)
    hash_target = target.with_suffix(".zip.sha256")
    if target.exists() and hash_target.exists():
        return target, hash_target.read_text().split()[0]
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(dir=target.parent, prefix=".package-")
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        members = package_members(database, storage, signer, capture_session)
        index = {
            "schema_version": "0.1.0",
            "session_id": capture_session.id,
            "created_at": rfc3339(capture_session.ended_at or capture_session.updated_at),
            "members": [
                {
                    "path": path,
                    "size": len(content),
                    "media_type": media_type(path),
                    "sha256": sha256_identifier(content),
                }
                for path, content in sorted(members.items())
            ],
        }
        members["package-index.json"] = canonical_bytes(index)
        members["signatures/package-index.server.sig"] = (
            signer.sign(DOMAINS["package_index"], index).encode("ascii") + b"\n"
        )
        with ZipFile(
            temporary,
            mode="w",
            compression=ZIP_DEFLATED,
            compresslevel=6,
            allowZip64=True,
        ) as archive:
            for path, content in sorted(members.items()):
                info = ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content)
        with temporary.open("rb") as package_file:
            os.fsync(package_file.fileno())
        with suppress(FileExistsError):
            os.link(temporary, target)
        package_hash = hash_path(target)
        hash_content = f"{package_hash}  {target.name}\n"
        write_once(hash_target, hash_content.encode("ascii"))
        fsync_directory(target.parent)
        capture_session.package_status = "available"
        append_audit_event(
            database,
            "evidence_package_generated",
            subject_id=capture_session.id,
            details={"package_hash": package_hash},
        )
        database.commit()
        return target, package_hash
    finally:
        temporary.unlink(missing_ok=True)


def package_members(
    database: Session,
    storage: DurableStorage,
    signer: ServerSigner,
    capture_session: CaptureSession,
) -> dict[str, bytes]:
    if (
        capture_session.manifest is None
        or capture_session.manifest_signature_hex is None
        or capture_session.capture_close is None
        or capture_session.capture_close_signature_hex is None
        or capture_session.client_public_key is None
        or capture_session.client_key_id is None
    ):
        raise ValueError("session is not ready for packaging")
    entries = list(
        database.scalars(
            select(ChainEntry)
            .where(ChainEntry.session_id == capture_session.id)
            .order_by(ChainEntry.sequence)
        )
    )
    receipts = list(
        database.scalars(
            select(Receipt)
            .where(Receipt.session_id == capture_session.id)
            .order_by(Receipt.sequence)
        )
    )
    artifacts = list(
        database.scalars(
            select(Artifact)
            .where(Artifact.session_id == capture_session.id)
            .order_by(Artifact.artifact_id)
        )
    )
    parts = list(
        database.scalars(
            select(ArtifactPart)
            .where(ArtifactPart.session_id == capture_session.id)
            .order_by(ArtifactPart.artifact_id, ArtifactPart.part_number)
        )
    )
    server_key_record = {
        "key_id": signer.key_id,
        "algorithm": "Ed25519",
        "public_key_hex": signer.public_key.hex(),
    }
    if signer.certificate is not None:
        server_key_record["certificate_path"] = (
            "signatures/server-key-certificate.json"
        )
    if signer.revocation_list is not None:
        server_key_record["revocation_list_path"] = (
            "signatures/server-key-revocations.json"
        )
    members = {
        "capture-manifest.json": canonical_bytes(capture_session.manifest),
        "chain/capture-close.json": canonical_bytes(capture_session.capture_close),
        "chain/entries.jsonl": json_lines(
            {
                "entry": entry.payload,
                "entry_hash": entry.entry_hash,
                "signature_hex": entry.signature_hex,
            }
            for entry in entries
        ),
        "chain/receipts.jsonl": json_lines(
            {
                "receipt": receipt.payload,
                "receipt_hash": receipt.receipt_hash,
                "signature_hex": receipt.signature_hex,
            }
            for receipt in receipts
        ),
        "signatures/capture-close.client.sig": (
            capture_session.capture_close_signature_hex.encode("ascii") + b"\n"
        ),
        "signatures/capture-manifest.server.sig": (
            capture_session.manifest_signature_hex.encode("ascii") + b"\n"
        ),
        "signatures/public-keys.json": canonical_bytes(
            {
                "schema_version": "0.1.0",
                "server": server_key_record,
                "client": {
                    "key_id": capture_session.client_key_id,
                    "algorithm": "Ed25519",
                    "public_key_hex": capture_session.client_public_key.hex(),
                },
            }
        ),
    }
    if signer.certificate is not None:
        members["signatures/server-key-certificate.json"] = canonical_bytes(
            signer.certificate
        )
    if signer.revocation_list is not None:
        members["signatures/server-key-revocations.json"] = canonical_bytes(
            signer.revocation_list
        )
    parts_by_artifact: dict[str, list[ArtifactPart]] = {}
    for part in parts:
        parts_by_artifact.setdefault(part.artifact_id, []).append(part)
    for artifact in artifacts:
        if artifact.status != "captured":
            continue
        members[artifact.path] = b"".join(
            storage.read(part.storage_key)
            for part in parts_by_artifact.get(artifact.artifact_id, [])
        )
    return members


def json_lines(values: Iterable[dict]) -> bytes:
    return b"".join(canonical_bytes(value) + b"\n" for value in values)


def media_type(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".sig": "application/octet-stream",
        ".webm": "video/webm",
        ".png": "image/png",
        ".html": "text/html",
        ".txt": "text/plain",
    }.get(suffix, "application/octet-stream")


def hash_path(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def write_once(target: Path, content: bytes) -> None:
    try:
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        if target.read_bytes() != content:
            raise
        return
    with os.fdopen(descriptor, "wb") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def rfc3339(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
