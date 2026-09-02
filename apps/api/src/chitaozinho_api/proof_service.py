from __future__ import annotations

import secrets
import shutil
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from chitaozinho_protocol import DOMAINS, canonical_bytes, sha256_identifier
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .audit import append_audit_event
from .config import Settings
from .models import (
    Attestation,
    CaptureSession,
    MerkleBatch,
    MerkleMembership,
    OtsComplement,
    TimestampAttempt,
)
from .proof_storage import ProofStorage, create_proof_storage
from .proofs import (
    MerkleLeaf,
    build_merkle_proofs,
    create_rfc3161_query,
    extract_rfc3161_chain,
    inspect_ots,
    request_rfc3161_timestamp,
    stamp_ots,
    upgrade_ots,
    verify_ots,
    verify_rfc3161_response,
    write_merkle_proof,
)
from .security import ServerSigner


class OtsPendingConfirmation(RuntimeError):
    pass


def timestamp_capture(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    capture_session: CaptureSession,
    *,
    commit: bool = True,
    proof_storage: ProofStorage | None = None,
) -> Attestation:
    proof_storage = proof_storage or create_proof_storage(settings)
    capture_session = lock_capture_sessions(
        database,
        [capture_session.id],
    )[0]
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
    prefix = f"sessions/{capture_session.id}/timestamp"
    query_key = f"{prefix}/attempt-{attempt_number:04d}.tsq"
    response_key = f"{prefix}/attempt-{attempt_number:04d}.tsr"
    chain_key = f"{prefix}/attempt-{attempt_number:04d}-tsa-chain.pem"
    with tempfile.TemporaryDirectory(prefix="chitaozinho-rfc3161-") as directory:
        root = Path(directory)
        query = root / "request.tsq"
        response = root / "response.tsr"
        create_rfc3161_query(capture_session.manifest_hash, query)
        status = "pending"
        details: dict[str, str] = {"request_path": query_key}
        error_message = None
        gen_time = None
        policy = None
        response_path = None
        chain_path = None
        if settings.tsa_url:
            try:
                request_rfc3161_timestamp(settings.tsa_url, query.read_bytes(), response)
                response_path = response_key
                details["response_path"] = response_path
                if settings.tsa_ca_bundle is None:
                    raise ValueError("TSA CA bundle is required to trust a response")
                chain = root / "tsa-chain.pem"
                extract_rfc3161_chain(response, chain)
                if settings.tsa_untrusted_chain is not None:
                    append_bundle(settings.tsa_untrusted_chain, chain)
                chain_path = chain_key
                details["chain_path"] = chain_path
                trust = root / "trust.pem"
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
                details["policy"] = policy
                details["serial"] = verified["serial"]
                status = "valid"
            except Exception as error:  # noqa: BLE001 - provider failures are persisted
                status = "failed"
                error_message = f"{type(error).__name__}: {error}"[:2000]
        proof_storage.put_once(query_key, query.read_bytes())
        if response.exists():
            proof_storage.put_once(response_key, response.read_bytes())
        if chain_path is not None:
            proof_storage.put_once(chain_key, chain.read_bytes())
    attempt = TimestampAttempt(
        session_id=capture_session.id,
        attempt_number=attempt_number,
        manifest_hash=capture_session.manifest_hash,
        status=status,
        query_path=query_key,
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
    append_audit_event(
        database,
        "timestamp_attempt_recorded",
        subject_id=capture_session.id,
        details={
            "attempt_number": attempt_number,
            "manifest_hash": capture_session.manifest_hash,
            "status": status,
        },
    )
    if commit:
        database.commit()
    return attestation


def create_merkle_batch(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    session_ids: list[str],
    *,
    submit_ots: bool,
    proof_storage: ProofStorage | None = None,
) -> MerkleBatch:
    proof_storage = proof_storage or create_proof_storage(settings)
    unique_ids = sorted(set(session_ids))
    if not unique_ids or len(unique_ids) > 100 or len(unique_ids) != len(session_ids):
        raise ValueError("Merkle batch requires 1 to 100 unique sessions")
    sessions = lock_capture_sessions(database, unique_ids)
    if len(sessions) != len(unique_ids) or any(
        session.manifest_hash is None for session in sessions
    ):
        raise ValueError("all Merkle sessions must have immutable manifests")
    leaves = [
        MerkleLeaf(session.manifest_hash or "", secrets.token_hex(32))
        for session in sessions
    ]
    proofs = build_merkle_proofs(leaves)
    batch_id = uuid.uuid4().hex
    root_key = f"merkle/{batch_id}/root.bin"
    proof_key = f"merkle/{batch_id}/root.bin.ots"
    with tempfile.TemporaryDirectory(prefix="chitaozinho-ots-stamp-") as directory:
        temporary_root = Path(directory)
        root_file = temporary_root / "root.bin"
        proof_file = temporary_root / "root.bin.ots"
        status = "not_submitted"
        if submit_ots:
            stamp_ots(
                proofs[0].root_hash,
                root_file,
                proof_file,
                [
                    value.strip()
                    for value in settings.ots_calendars.split(",")
                    if value.strip()
                ],
            )
            status = "pending_confirmation"
        else:
            root_file.write_bytes(bytes.fromhex(proofs[0].root_hash[7:]))
        proof_storage.put_once(root_key, root_file.read_bytes())
        if proof_file.exists():
            proof_storage.put_once(proof_key, proof_file.read_bytes())
    batch = MerkleBatch(
        id=batch_id,
        root_hash=proofs[0].root_hash,
        status=status,
        root_path=root_key,
        ots_proof_path=proof_key if submit_ots else None,
        created_at=datetime.now(UTC),
    )
    database.add(batch)
    for capture_session, proof in zip(sessions, proofs, strict=True):
        membership_key = (
            f"sessions/{capture_session.id}/merkle/{batch_id}.proof.json"
        )
        with tempfile.TemporaryDirectory(
            prefix="chitaozinho-merkle-membership-"
        ) as directory:
            membership_path = Path(directory) / "membership.json"
            write_merkle_proof(proof, membership_path)
            proof_storage.put_once(membership_key, membership_path.read_bytes())
        database.add(
            MerkleMembership(
                batch_id=batch_id,
                session_id=capture_session.id,
                proof_path=membership_key,
                proof=proof.as_dict(),
            )
        )
        capture_session.blockchain_status = status
        append_attestation(
            database,
            signer,
            capture_session,
            blockchain={
                "merkle_proof_path": membership_key,
                **(
                    {"ots_proof_path": proof_key}
                    if submit_ots
                    else {}
                ),
                "checked_at": rfc3339(datetime.now(UTC)),
            },
        )
    append_audit_event(
        database,
        "merkle_batch_created",
        subject_id=batch.id,
        details={
            "root_hash": batch.root_hash,
            "session_count": len(sessions),
            "status": status,
        },
    )
    database.commit()
    return batch


def upgrade_merkle_batch(
    database: Session,
    settings: Settings,
    signer: ServerSigner,
    batch: MerkleBatch,
    *,
    proof_storage: ProofStorage | None = None,
) -> OtsComplement:
    proof_storage = proof_storage or create_proof_storage(settings)
    batch_statement = select(MerkleBatch).where(MerkleBatch.id == batch.id)
    if database.get_bind().dialect.name == "postgresql":
        batch_statement = batch_statement.with_for_update()
    locked_batch = database.scalar(batch_statement)
    if locked_batch is None:
        raise ValueError("Merkle batch no longer exists")
    batch = locked_batch
    if batch.ots_proof_path is None:
        raise ValueError("Merkle batch has no original OpenTimestamps proof")
    latest_complement = database.scalar(
        select(OtsComplement)
        .where(OtsComplement.batch_id == batch.id)
        .order_by(OtsComplement.sequence.desc())
        .limit(1)
    )
    sequence = (latest_complement.sequence if latest_complement is not None else 0) + 1
    source_key = (
        latest_complement.proof_path
        if latest_complement is not None
        else batch.ots_proof_path
    )
    complement_key = f"merkle/{batch.id}/complements/upgrade-{sequence:04d}.ots"
    with tempfile.TemporaryDirectory(prefix="chitaozinho-ots-upgrade-") as directory:
        temporary = Path(directory)
        source = temporary / "source.ots"
        complement_path = temporary / "complement.ots"
        root_file = temporary / "root.bin"
        source.write_bytes(proof_storage.read(source_key))
        root_file.write_bytes(proof_storage.read(batch.root_path))
        if not upgrade_ots(source, complement_path):
            raise OtsPendingConfirmation("OpenTimestamps proof is still pending")
        proof_status = inspect_ots(complement_path)
        if (
            proof_status == "bitcoin_attestation_available"
            and settings.ots_bitcoin_node_url is not None
        ):
            proof_status = verify_ots(
                root_file,
                complement_path,
                settings.ots_bitcoin_node_url,
            )
        complement_bytes = complement_path.read_bytes()
        proof_hash = sha256_identifier(complement_bytes)
        proof_storage.put_once(complement_key, complement_bytes)
    complement = OtsComplement(
        id=f"{batch.id}-{sequence:04d}",
        batch_id=batch.id,
        sequence=sequence,
        proof_path=complement_key,
        proof_hash=proof_hash,
        status=proof_status,
        created_at=datetime.now(UTC),
    )
    database.add(complement)
    batch.status = proof_status
    memberships = list(
        database.scalars(
            select(MerkleMembership).where(MerkleMembership.batch_id == batch.id)
        )
    )
    sessions = lock_capture_sessions(
        database,
        sorted(membership.session_id for membership in memberships),
    )
    sessions_by_id = {capture_session.id: capture_session for capture_session in sessions}
    if len(sessions_by_id) != len(memberships):
        raise RuntimeError("Merkle membership references a missing session")
    for membership in memberships:
        capture_session = sessions_by_id[membership.session_id]
        capture_session.blockchain_status = proof_status
        append_attestation(
            database,
            signer,
            capture_session,
            blockchain={
                "merkle_proof_path": membership.proof_path,
                "ots_proof_path": batch.ots_proof_path,
                "ots_complement_path": complement.proof_path,
                "ots_complement_hash": proof_hash,
                "checked_at": rfc3339(datetime.now(UTC)),
            },
        )
    append_audit_event(
        database,
        "ots_complement_created",
        subject_id=batch.id,
        details={
            "proof_hash": proof_hash,
            "status": proof_status,
            "sequence": sequence,
        },
    )
    database.commit()
    return complement


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
        "schema_version": "0.1.1",
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


def lock_capture_sessions(
    database: Session,
    session_ids: list[str],
) -> list[CaptureSession]:
    statement = (
        select(CaptureSession)
        .where(CaptureSession.id.in_(session_ids))
        .order_by(CaptureSession.id)
    )
    if database.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update()
    return list(database.scalars(statement))


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
