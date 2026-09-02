"""Add beta storage expiry and persistent magic-link throttling.

Revision ID: 0006_beta_retention
Revises: 0005_magic_link_auth
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_beta_retention"
down_revision: str | None = "0005_magic_link_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "capture_sessions",
        sa.Column("storage_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "capture_sessions",
        sa.Column("storage_expired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "magic_link_request_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_magic_link_request_attempts_email_hash"),
        "magic_link_request_attempts",
        ["email_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_magic_link_request_attempts_ip_hash"),
        "magic_link_request_attempts",
        ["ip_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_magic_link_request_attempts_created_at"),
        "magic_link_request_attempts",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_magic_link_request_attempts_created_at"),
        table_name="magic_link_request_attempts",
    )
    op.drop_index(
        op.f("ix_magic_link_request_attempts_ip_hash"),
        table_name="magic_link_request_attempts",
    )
    op.drop_index(
        op.f("ix_magic_link_request_attempts_email_hash"),
        table_name="magic_link_request_attempts",
    )
    op.drop_table("magic_link_request_attempts")
    op.drop_column("capture_sessions", "storage_expired_at")
    op.drop_column("capture_sessions", "storage_expires_at")
