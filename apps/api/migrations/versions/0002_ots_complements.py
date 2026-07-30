"""Preserve OpenTimestamps upgrades as immutable complements."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_ots_complements"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ots_complements",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(64),
            sa.ForeignKey("merkle_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("proof_path", sa.Text(), nullable=False),
        sa.Column("proof_hash", sa.String(71), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("batch_id", "sequence"),
    )
    op.create_index("ix_ots_complements_batch_id", "ots_complements", ["batch_id"])


def downgrade() -> None:
    op.drop_table("ots_complements")
