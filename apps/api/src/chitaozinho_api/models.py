from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CaptureSession(Base):
    __tablename__ = "capture_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    server_challenge: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    client_key_id: Mapped[str | None] = mapped_column(String(128))
    client_public_key: Mapped[bytes | None] = mapped_column(LargeBinary(32))
    last_receipt_hash: Mapped[str | None] = mapped_column(String(71))
    capture_close: Mapped[dict | None] = mapped_column(JSON)
    capture_close_signature_hex: Mapped[str | None] = mapped_column(String(128))
    manifest: Mapped[dict | None] = mapped_column(JSON)
    manifest_hash: Mapped[str | None] = mapped_column(String(71))
    manifest_signature_hex: Mapped[str | None] = mapped_column(String(128))
    server_key_id: Mapped[str | None] = mapped_column(String(128))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    package_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_generated"
    )
    timestamp_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_requested"
    )
    blockchain_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="not_submitted"
    )
    storage_status: Mapped[str] = mapped_column(String(32), nullable=False, default="staging")


class ChainEntry(Base):
    __tablename__ = "chain_entries"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence"),
        UniqueConstraint("session_id", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entry_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature_hex: Mapped[str] = mapped_column(String(128), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ArtifactPart(Base):
    __tablename__ = "artifact_parts"
    __table_args__ = (
        UniqueConstraint("session_id", "artifact_id", "part_number"),
        UniqueConstraint("session_id", "idempotency_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    part_number: Mapped[int] = mapped_column(Integer, nullable=False)
    part_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    persistence_state: Mapped[str] = mapped_column(String(32), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)


class Artifact(Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("session_id", "artifact_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    artifact_id: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    part_count: Mapped[int] = mapped_column(Integer, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    method: Mapped[str] = mapped_column(String(128), nullable=False)
    provenance: Mapped[str] = mapped_column(String(32), nullable=False)
    completed_entry_hash: Mapped[str] = mapped_column(String(71), nullable=False)


class Receipt(Base):
    __tablename__ = "receipts"
    __table_args__ = (UniqueConstraint("session_id", "sequence"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    signature_hex: Mapped[str] = mapped_column(String(128), nullable=False)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class TimestampAttempt(Base):
    __tablename__ = "timestamp_attempts"
    __table_args__ = (UniqueConstraint("session_id", "attempt_number"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    manifest_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    query_path: Mapped[str] = mapped_column(Text, nullable=False)
    response_path: Mapped[str | None] = mapped_column(Text)
    chain_path: Mapped[str | None] = mapped_column(Text)
    gen_time: Mapped[str | None] = mapped_column(String(128))
    policy: Mapped[str | None] = mapped_column(String(256))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MerkleBatch(Base):
    __tablename__ = "merkle_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    root_hash: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    root_path: Mapped[str] = mapped_column(Text, nullable=False)
    ots_proof_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MerkleMembership(Base):
    __tablename__ = "merkle_memberships"
    __table_args__ = (UniqueConstraint("batch_id", "session_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("merkle_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proof_path: Mapped[str] = mapped_column(Text, nullable=False)
    proof: Mapped[dict] = mapped_column(JSON, nullable=False)


class OtsComplement(Base):
    __tablename__ = "ots_complements"
    __table_args__ = (UniqueConstraint("batch_id", "sequence"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("merkle_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    proof_path: Mapped[str] = mapped_column(Text, nullable=False)
    proof_hash: Mapped[str] = mapped_column(String(71), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Attestation(Base):
    __tablename__ = "attestations"
    __table_args__ = (
        UniqueConstraint("session_id", "sequence"),
        UniqueConstraint("document_hash"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("capture_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_attestation_hash: Mapped[str | None] = mapped_column(String(71))
    document: Mapped[dict] = mapped_column(JSON, nullable=False)
    document_hash: Mapped[str] = mapped_column(String(71), nullable=False)
    signature_hex: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
