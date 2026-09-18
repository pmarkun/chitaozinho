"""Separate evidence custody from hash registration without changing old sessions."""

import sqlalchemy as sa
from alembic import op

revision = "0007_hash_only"
down_revision = "0006_beta_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        sa.Column(
            "evidence_mode",
            sa.String(16),
            nullable=False,
            server_default="remote",
        ),
    )


def downgrade() -> None:
    op.drop_column("capture_sessions", "evidence_mode")
