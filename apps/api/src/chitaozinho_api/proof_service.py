from __future__ import annotations

import secrets
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path

from chitaozinho_protocol import DOMAINS, canonical_bytes, sha256_identifier
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import Settings
from .models import (
    Attestation,
    CaptureSession,
    MerkleBatch,
    MerkleMembership,
    TimestampAttempt,
)
from .proofs import (
    MerkleLeaf,
    build_merkle_proofs,
    create_rfc3161_query,
    extract_rfc3161_chain,
    request_rfc3161_timestamp,
    stamp_ots,
    verify_rfc3161_response,
    write_merkle_proof,
)
from .security import ServerSigner


def timestamp_capture(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    capture_session: CaptureSession,
) -> Attestation:
    if capture_session.manifest_hash is None:
        raise ValueError("session has no immutable manifest")
    attempt_number = (
        database.scalar(
            select(func.count(TimestampAttempt.id)).where(
                TimestampAttempt.session_id == capture_session.id
            )
        )
        or 0
    ) + 1
    root = settings.proofs_path / capture_session.id / "timestamp"
    query = root / f"attempt-{attempt_number:04d}.tsq"
    response = root / f"attempt-{attempt_number:04d}.tsr"
    create_rfc3161_query(capture_session.manifest_hash, query)
    status = "pending"
    details: dict[str, str] = {"request_path": relative_proof_path(settings, query)}
    error_message = None
    gen_time = None
    policy = None
    response_path = None
    chain_path = None
    if settings.tsa_url:
        try:
            request_rfc3161_timestamp(settings.tsa_url, query.read_bytes(), response)
            response_path = relative_proof_path(settings, response)
            details["response_path"] = response_path
            if settings.tsa_ca_bundle is None:
                raise ValueError("TSA CA bundle is required to trust a response")
            chain = root / f"attempt-{attempt_number:04d}-tsa-chain.pem"
            extract_rfc3161_chain(response, chain)
            if settings.tsa_untrusted_chain is not None:
                append_bundle(settings.tsa_untrusted_chain, chain)
            chain_path = relative_proof_path(settings, chain)
            details["chain_path"] = chain_path
            trust = root / f"attempt-{attempt_number:04d}-trust.pem"
            copy_bundles_new(
                [
                    settings.tsa_ca_bundle,
                    *(
                        [settings.tsa_crl_bundle]
                        if settings.tsa_crl_bundle is not None
                        else []
                    ),
                ],
                trust,
            )
            verified = verify_rfc3161_response(
                query,
                response,
                trust,
                untrusted_chain=chain,
                crl_check=settings.tsa_crl_bundle is not None,
            )
            gen_time = verified["gen_time"]
            policy = verified["policy"]
            details["gen_time"] = gen_time
            status = "valid"
        except Exception as error:  # noqa: BLE001 - provider failures are persisted
            status = "failed"
            error_message = f"{type(error).__name__}: {error}"[:2000]
    attempt = TimestampAttempt(
        session_id=capture_session.id,
        attempt_number=attempt_number,
        manifest_hash=capture_session.manifest_hash,
        status=status,
        query_path=relative_proof_path(settings, query),
        response_path=response_path,
        chain_path=chain_path,
        gen_time=gen_time,
        policy=policy,
        error=error_message,
        created_at=datetime.now(UTC),
    )
    database.add(attempt)
    capture_session.timestamp_status = status
    attestation = append_attestation(
        database,
        signer,
        capture_session,
        timestamp=details,
    )
    database.commit()
    return attestation


def create_merkle_batch(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    session_ids: list[str],
    *,
    submit_ots: bool,
) -> MerkleBatch:
    unique_ids = sorted(set(session_ids))
    if not unique_ids or len(unique_ids) > 100 or len(unique_ids) != len(session_ids):
        raise ValueError("Merkle batch requires 1 to 100 unique sessions")
    sessions = [
        database.get(CaptureSession, session_id) for session_id in unique_ids
    ]
    if any(session is None or session.manifest_hash is None for session in sessions):
        raise ValueError("all Merkle sessions must have immutable manifests")
    typed_sessions = [session for session in sessions if session is not None]
    leaves = [
        MerkleLeaf(session.manifest_hash or "", secrets.token_hex(32))
        for session in typed_sessions
    ]
    proofs = build_merkle_proofs(leaves)
    batch_id = uuid.uuid4().hex
    root = settings.proofs_path / "merkle" / batch_id
    root_file = root / "root.bin"
    proof_file = root / "root.bin.ots"
    status = "not_submitted"
    if submit_ots:
        stamp_ots(
            proofs[0].root_hash,
            root_file,
            proof_file,
            [value for value in settings.ots_calendars.split(",") if value],
        )
        status = "pending_confirmation"
    else:
        root_file.parent.mkdir(parents=True, exist_ok=True)
        with root_file.open("xb") as output:
            output.write(bytes.fromhex(proofs[0].root_hash[7:]))
    batch = MerkleBatch(
        id=batch_id,
        root_hash=proofs[0].root_hash,
        status=status,
        root_path=relative_proof_path(settings, root_file),
        ots_proof_path=(
            relative_proof_path(settings, proof_file) if proof_file.exists() else None
        ),
        created_at=datetime.now(UTC),
    )
    database.add(batch)
    for capture_session, proof in zip(typed_sessions, proofs, strict=True):
        membership_path = root / f"{capture_session.id}.proof.json"
        write_merkle_proof(proof, membership_path)
        database.add(
            MerkleMembership(
                batch_id=batch_id,
                session_id=capture_session.id,
                proof_path=relative_proof_path(settings, membership_path),
                proof=proof.as_dict(),
            )
        )
        capture_session.blockchain_status = status
        append_attestation(
            database,
            signer,
            capture_session,
            blockchain={
                "merkle_proof_path": relative_proof_path(settings, membership_path),
                **(
                    {"ots_proof_path": relative_proof_path(settings, proof_file)}
                    if proof_file.exists()
                    else {}
                ),
                "checked_at": rfc3339(datetime.now(UTC)),
            },
        )
    database.commit()
    return batch


def append_attestation(
    database: Session,
    signer: ServerSigner,
    capture_session: CaptureSession,
    *,
    timestamp: dict[str, str] | None = None,
    blockchain: dict[str, str] | None = None,
) -> Attestation:
    previous = database.scalar(
        select(Attestation)
        .where(Attestation.session_id == capture_session.id)
        .order_by(Attestation.sequence.desc())
    )
    sequence = 0 if previous is None else previous.sequence + 1
    attestation_id = f"{capture_session.id}-{sequence + 1:04d}"
    document = {
        "schema_version": "0.1.0",
        "attestation_id": attestation_id,
        "previous_attestation_hash": (
            None if previous is None else previous.document_hash
        ),
        "manifest_hash": capture_session.manifest_hash,
        "created_at": rfc3339(datetime.now(UTC)),
        "issuer_key_id": signer.key_id,
        "timestamp_status": capture_session.timestamp_status,
        "blockchain_status": capture_session.blockchain_status,
    }
    if timestamp is not None:
        document["timestamp"] = timestamp
    if blockchain is not None:
        document["blockchain"] = blockchain
    document_hash = sha256_identifier(canonical_bytes(document))
    attestation = Attestation(
        id=attestation_id,
        session_id=capture_session.id,
        sequence=sequence,
        previous_attestation_hash=document["previous_attestation_hash"],
        document=document,
        document_hash=document_hash,
        signature_hex=signer.sign(DOMAINS["attestation"], document),
        created_at=datetime.now(UTC),
    )
    database.add(attestation)
    return attestation


def relative_proof_path(settings: Settings, path: Path) -> str:
    return path.relative_to(settings.proofs_path).as_posix()


def copy_bundles_new(sources: list[Path], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as output_file:
        for source in sources:
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, output_file)
            output_file.write(b"\n")


def append_bundle(source: Path, target: Path) -> None:
    with source.open("rb") as input_file, target.open("ab") as output_file:
        shutil.copyfileobj(input_file, output_file)
        output_file.write(b"\n")


def rfc3339(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
