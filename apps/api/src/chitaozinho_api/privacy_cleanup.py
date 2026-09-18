"""Privacy retention and operator-assisted account erasure (dry run by default)."""

from __future__ import annotations

import argparse
import calendar
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from .audit import AUDIT_ADVISORY_LOCK_ID, append_audit_event, verify_audit_chain
from .config import Settings
from .database import create_database_engine
from .models import (
    AccessToken,
    Artifact,
    ArtifactPart,
    Attestation,
    AuditCheckpoint,
    AuditEvent,
    CaptureSession,
    ChainEntry,
    Incident,
    Job,
    MagicLinkRequestAttempt,
    MagicLinkToken,
    MerkleBatch,
    MerkleMembership,
    OtsComplement,
    Receipt,
    TimestampAttempt,
    User,
)
from .proof_storage import ProofStorage, create_proof_storage


def twelve_months_ago(now: datetime) -> datetime:
    year = now.year - 1
    return now.replace(year=year, day=min(now.day, calendar.monthrange(year, now.month)[1]))


def retire_audit_prefix(database: Session, cutoff: datetime, *, apply: bool) -> int:
    if database.get_bind().dialect.name == "postgresql":
        database.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": AUDIT_ADVISORY_LOCK_ID})
    verify_audit_chain(database)
    first_retained = database.scalar(
        select(func.min(AuditEvent.sequence)).where(AuditEvent.created_at > cutoff)
    )
    statement = select(AuditEvent).where(AuditEvent.created_at <= cutoff)
    if first_retained is not None:
        statement = statement.where(AuditEvent.sequence < first_retained)
    boundary = database.scalar(statement.order_by(AuditEvent.sequence.desc()).limit(1))
    if boundary is None:
        return 0
    count = (
        database.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.sequence <= boundary.sequence)
        )
        or 0
    )
    if apply:
        checkpoint = database.get(AuditCheckpoint, 1)
        if checkpoint is None:
            checkpoint = AuditCheckpoint(
                id=1, sequence=boundary.sequence, event_hash=boundary.event_hash
            )
            database.add(checkpoint)
        else:
            checkpoint.sequence, checkpoint.event_hash = boundary.sequence, boundary.event_hash
        database.flush()
        # This is the sole retirement path. DB triggers still reject updates and
        # deletion of recent/uncheckpointed records; retained hashes are untouched.
        database.execute(delete(AuditEvent).where(AuditEvent.sequence <= boundary.sequence))
        verify_audit_chain(database)
    return count


def purge_session(
    database: Session, proofs: ProofStorage, capture: CaptureSession, *, apply: bool
) -> None:
    if capture.evidence_mode != "hash_only" and capture.storage_expired_at is None:
        raise RuntimeError("legacy object retention must finish before metadata erasure")
    batch_ids = list(
        database.scalars(
            select(MerkleMembership.batch_id).where(MerkleMembership.session_id == capture.id)
        )
    )
    # Lock shared batches before deciding whether this is the last membership.
    if batch_ids:
        list(
            database.scalars(
                select(MerkleBatch)
                .where(MerkleBatch.id.in_(batch_ids))
                .order_by(MerkleBatch.id)
                .with_for_update()
            )
        )
    scope_ids = [capture.id, *batch_ids]
    jobs = list(
        database.scalars(select(Job).where(Job.subject_id.in_(scope_ids)).with_for_update())
    )
    if any(job.status == "running" for job in jobs):
        raise RuntimeError("capture or shared proof has a running job; retry after completion")
    if not apply:
        return
    # Object deletion precedes DB deletion. A partial failure keeps the metadata
    # so the same exact scopes can be retried on the next daily run.
    proofs.delete_scope("sessions", capture.id)
    for model in (
        ArtifactPart,
        Artifact,
        Receipt,
        Incident,
        TimestampAttempt,
        Attestation,
        ChainEntry,
        MerkleMembership,
    ):
        database.execute(delete(model).where(model.session_id == capture.id))
    database.execute(delete(Job).where(Job.subject_id == capture.id))
    database.delete(capture)
    database.flush()
    for batch_id in batch_ids:
        remaining = database.scalar(
            select(func.count())
            .select_from(MerkleMembership)
            .where(MerkleMembership.batch_id == batch_id)
        )
        if remaining:
            continue
        proofs.delete_scope("merkle", batch_id)
        database.execute(delete(OtsComplement).where(OtsComplement.batch_id == batch_id))
        database.execute(delete(Job).where(Job.subject_id == batch_id))
        database.execute(delete(MerkleBatch).where(MerkleBatch.id == batch_id))


def cleanup_personal_data(
    factory: sessionmaker[Session],
    proofs: ProofStorage,
    *,
    now: datetime | None = None,
    apply: bool = False,
    user_id: str | None = None,
) -> dict[str, int]:
    current = now or datetime.now(UTC)
    result = {"sessions": 0, "accounts": 0, "security_records": 0, "failures": 0}
    # Each session is one transaction. A failure cannot falsely mark another
    # session deleted or remove shared proofs still needed by retained members.
    with factory() as database:
        statement = select(CaptureSession.id).order_by(CaptureSession.id)
        if user_id is not None:
            if database.get(User, user_id) is None:
                raise ValueError("account not found")
            statement = statement.where(CaptureSession.owner_user_id == user_id)
        else:
            statement = statement.where(CaptureSession.created_at <= twelve_months_ago(current))
        ids = list(database.scalars(statement))
    for session_id in ids:
        try:
            with factory.begin() as database:
                capture = database.scalar(
                    select(CaptureSession).where(CaptureSession.id == session_id).with_for_update()
                )
                if capture is not None:
                    purge_session(database, proofs, capture, apply=apply)
                    result["sessions"] += 1
        except Exception:
            result["failures"] += 1
    with factory.begin() as database:
        user = None
        if user_id is not None:
            user = database.scalar(select(User).where(User.id == user_id).with_for_update())
        cutoff = current - timedelta(days=30)
        result["security_records"] += retire_audit_prefix(database, cutoff, apply=apply)
        for model, condition in (
            (MagicLinkRequestAttempt, MagicLinkRequestAttempt.created_at <= cutoff),
            (MagicLinkToken, MagicLinkToken.expires_at <= current),
            (AccessToken, AccessToken.expires_at <= current),
            (
                Job,
                (Job.updated_at <= cutoff)
                & Job.status.in_(["completed", "failed"])
                & ~Job.subject_id.in_(select(MerkleBatch.id)),
            ),
        ):
            result["security_records"] += (
                database.scalar(select(func.count()).select_from(model).where(condition)) or 0
            )
            if apply:
                database.execute(delete(model).where(condition))
        if user_id is not None and not result["failures"]:
            # Recheck under account lock: never delete an account while newly
            # created captures still reference it. Operator can retry safely.
            remaining = database.scalar(
                select(func.count())
                .select_from(CaptureSession)
                .where(CaptureSession.owner_user_id == user_id)
            )
            if apply and remaining:
                raise RuntimeError("account gained new captures; retry erasure")
            if user is not None:
                if apply:
                    database.execute(
                        delete(MagicLinkToken).where(MagicLinkToken.user_id == user_id)
                    )
                    database.execute(delete(AccessToken).where(AccessToken.user_id == user_id))
                    database.delete(user)
                result["accounts"] = 1
        if apply:
            append_audit_event(
                database, "privacy_retention_completed", subject_id=None, details=result.copy()
            )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--user-id", help="Exact account ID, after verifying the requester's identity"
    )
    args = parser.parse_args()
    settings = Settings()
    if settings.env != "beta":
        raise RuntimeError("privacy cleanup is restricted to beta")
    factory = sessionmaker(create_database_engine(settings), expire_on_commit=False)
    result = cleanup_personal_data(
        factory, create_proof_storage(settings), apply=args.apply, user_id=args.user_id
    )
    print({"apply": args.apply, **result})
    if result["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
