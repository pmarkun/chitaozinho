from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from chitaozinho_protocol import DOMAINS, canonical_bytes, sha256_identifier
from sqlalchemy import select
from sqlalchemy.orm import Session

from .audit import append_audit_event
from .config import Settings
from .models import Attestation, CaptureSession
from .retention import protect_final_artifact
from .security import ServerSigner
from .storage import DurableStorage

INDEX_PATH = "proof-bundle-index.json"
INDEX_SIGNATURE_PATH = "signatures/proof-bundle-index.server.sig"
ATTESTATIONS_PATH = "attestations.jsonl"


def ensure_proof_bundle(
    database: Session,
    settings: Settings,
    storage: DurableStorage,
    signer: ServerSigner,
    capture_session: CaptureSession,
) -> tuple[Path, str, str]:
    if capture_session.manifest_hash is None:
        raise ValueError("session has no immutable manifest")
    attestations = list(
        database.scalars(
            select(Attestation)
            .where(Attestation.session_id == capture_session.id)
            .order_by(Attestation.sequence)
        )
    )
    if not attestations:
        raise ValueError("session has no external attestations")
    latest_hash = attestations[-1].document_hash.removeprefix("sha256:")
    target = (
        settings.proofs_path
        / "bundles"
        / capture_session.id
        / f"{latest_hash}.zip"
    )
    if target.exists():
        bundle_hash = sha256_identifier(target.read_bytes())
        storage_status = protect_final_artifact(
            database,
            settings,
            storage,
            capture_session,
            name=f"proof-bundle-{latest_hash}.zip",
            path=target,
            digest=bundle_hash,
        )
        return target, bundle_hash, storage_status
    members = proof_bundle_members(settings, attestations)
    index = {
        "schema_version": "0.1.0",
        "session_id": capture_session.id,
        "manifest_hash": capture_session.manifest_hash,
        "created_at": rfc3339(datetime.now(UTC)),
        "members": [
            {
                "path": path,
                "size": len(content),
                "sha256": sha256_identifier(content),
            }
            for path, content in sorted(members.items())
        ],
    }
    members[INDEX_PATH] = canonical_bytes(index)
    members[INDEX_SIGNATURE_PATH] = (
        signer.sign(DOMAINS["proof_bundle_index"], index).encode("ascii") + b"\n"
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=target.parent,
        prefix=".proof-bundle-",
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
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
        with suppress(FileExistsError):
            os.link(temporary, target)
        bundle_hash = sha256_identifier(target.read_bytes())
        append_audit_event(
            database,
            "proof_bundle_generated",
            subject_id=capture_session.id,
            details={
                "bundle_hash": bundle_hash,
                "latest_attestation_hash": attestations[-1].document_hash,
            },
        )
        database.commit()
        storage_status = protect_final_artifact(
            database,
            settings,
            storage,
            capture_session,
            name=f"proof-bundle-{latest_hash}.zip",
            path=target,
            digest=bundle_hash,
        )
        return target, bundle_hash, storage_status
    finally:
        temporary.unlink(missing_ok=True)


def proof_bundle_members(
    settings: Settings,
    attestations: list[Attestation],
) -> dict[str, bytes]:
    records = [
        {
            "document": attestation.document,
            "document_hash": attestation.document_hash,
            "signature_hex": attestation.signature_hex,
        }
        for attestation in attestations
    ]
    members = {
        ATTESTATIONS_PATH: b"".join(
            canonical_bytes(record) + b"\n" for record in records
        )
    }
    for attestation in attestations:
        for path in referenced_proof_paths(attestation.document):
            if path in members:
                continue
            source = checked_proof_path(settings.proofs_path, path)
            members[path] = source.read_bytes()
    return members


def referenced_proof_paths(document: dict) -> set[str]:
    paths: set[str] = set()
    for section_name in ("timestamp", "blockchain"):
        section = document.get(section_name)
        if not isinstance(section, dict):
            continue
        for key, value in section.items():
            if key.endswith("_path") and isinstance(value, str):
                paths.add(value)
    return paths


def checked_proof_path(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or not path.parts
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError(f"unsafe proof path: {relative}")
    target = root.joinpath(*path.parts)
    if not target.is_file():
        raise ValueError(f"referenced proof is missing: {relative}")
    return target


def rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
