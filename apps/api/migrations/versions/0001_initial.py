"""Create the initial append-oriented evidence schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "capture_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("server_challenge", sa.String(256), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("next_sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_key_id", sa.String(128)),
        sa.Column("client_public_key", sa.LargeBinary(32)),
        sa.Column("last_receipt_hash", sa.String(71)),
        sa.Column("capture_close", sa.JSON()),
        sa.Column("capture_close_signature_hex", sa.String(128)),
        sa.Column("manifest", sa.JSON()),
        sa.Column("manifest_hash", sa.String(71)),
        sa.Column("manifest_signature_hex", sa.String(128)),
        sa.Column("server_key_id", sa.String(128)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "package_status",
            sa.String(32),
            nullable=False,
            server_default="not_generated",
        ),
        sa.Column(
            "timestamp_status",
            sa.String(32),
            nullable=False,
            server_default="not_requested",
        ),
        sa.Column(
            "blockchain_status",
            sa.String(32),
            nullable=False,
            server_default="not_submitted",
        ),
        sa.Column(
            "storage_status", sa.String(32), nullable=False, server_default="staging"
        ),
    )
    create_session_child_tables()
    create_proof_tables()


def create_session_child_tables() -> None:
    op.create_table(
        "chain_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(71), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature_hex", sa.String(128), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "sequence"),
        sa.UniqueConstraint("session_id", "idempotency_key"),
    )
    op.create_index("ix_chain_entries_session_id", "chain_entries", ["session_id"])
    op.create_table(
        "artifact_parts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_id", sa.String(128), nullable=False),
        sa.Column("part_number", sa.Integer(), nullable=False),
        sa.Column("part_hash", sa.String(71), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("persistence_state", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.UniqueConstraint("session_id", "artifact_id", "part_number"),
        sa.UniqueConstraint("session_id", "idempotency_key"),
    )
    op.create_index("ix_artifact_parts_session_id", "artifact_parts", ["session_id"])
    op.create_table(
        "artifacts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_id", sa.String(128), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("part_count", sa.Integer(), nullable=False),
        sa.Column("artifact_hash", sa.String(71), nullable=False),
        sa.Column("media_type", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("method", sa.String(128), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("completed_entry_hash", sa.String(71), nullable=False),
        sa.UniqueConstraint("session_id", "artifact_id"),
    )
    op.create_index("ix_artifacts_session_id", "artifacts", ["session_id"])
    op.create_table(
        "receipts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("receipt_hash", sa.String(71), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("signature_hex", sa.String(128), nullable=False),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_index("ix_receipts_session_id", "receipts", ["session_id"])
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_incidents_session_id", "incidents", ["session_id"])


def create_proof_tables() -> None:
    op.create_table(
        "timestamp_attempts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(71), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("query_path", sa.Text(), nullable=False),
        sa.Column("response_path", sa.Text()),
        sa.Column("chain_path", sa.Text()),
        sa.Column("gen_time", sa.String(128)),
        sa.Column("policy", sa.String(256)),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "attempt_number"),
    )
    op.create_index(
        "ix_timestamp_attempts_session_id", "timestamp_attempts", ["session_id"]
    )
    op.create_table(
        "merkle_batches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("root_hash", sa.String(71), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("root_path", sa.Text(), nullable=False),
        sa.Column("ots_proof_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "merkle_memberships",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "batch_id",
            sa.String(64),
            sa.ForeignKey("merkle_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("proof_path", sa.Text(), nullable=False),
        sa.Column("proof", sa.JSON(), nullable=False),
        sa.UniqueConstraint("batch_id", "session_id"),
    )
    op.create_index(
        "ix_merkle_memberships_batch_id", "merkle_memberships", ["batch_id"]
    )
    op.create_index(
        "ix_merkle_memberships_session_id", "merkle_memberships", ["session_id"]
    )
    op.create_table(
        "attestations",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(64),
            sa.ForeignKey("capture_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("previous_attestation_hash", sa.String(71)),
        sa.Column("document", sa.JSON(), nullable=False),
        sa.Column("document_hash", sa.String(71), nullable=False, unique=True),
        sa.Column("signature_hex", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "sequence"),
    )
    op.create_index("ix_attestations_session_id", "attestations", ["session_id"])


def downgrade() -> None:
    for table in [
        "attestations",
        "merkle_memberships",
        "merkle_batches",
        "timestamp_attempts",
        "incidents",
        "receipts",
        "artifacts",
        "artifact_parts",
        "chain_entries",
        "capture_sessions",
    ]:
        op.drop_table(table)
