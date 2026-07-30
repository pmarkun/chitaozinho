"""Represent unavailable and partial capture artifacts explicitly."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_partial_artifacts"
down_revision: str | None = "0003_audit_and_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("artifacts") as batch:
        batch.alter_column(
            "artifact_hash",
            existing_type=sa.String(71),
            nullable=True,
        )
        batch.add_column(sa.Column("reason", sa.Text()))


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch:
        batch.drop_column("reason")
        batch.alter_column(
            "artifact_hash",
            existing_type=sa.String(71),
            nullable=False,
        )
