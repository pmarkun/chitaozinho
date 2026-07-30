"""Add durable jobs and database-protected append-only audit events."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_audit_and_jobs"
down_revision: str | None = "0002_ots_complements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("sequence", sa.Integer(), nullable=False, unique=True),
        sa.Column("previous_event_hash", sa.String(71)),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128)),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("event_hash", sa.String(71), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_subject_id", "audit_events", ["subject_id"])
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("subject_id", sa.String(128)),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON()),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text()),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_jobs_subject_id", "jobs", ["subject_id"])
    install_append_only_triggers()


def install_append_only_triggers() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        op.execute(
            """
            CREATE TRIGGER audit_events_no_update
            BEFORE UPDATE ON audit_events
            BEGIN
              SELECT RAISE(ABORT, 'audit_events is append-only');
            END
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_no_delete
            BEFORE DELETE ON audit_events
            BEGIN
              SELECT RAISE(ABORT, 'audit_events is append-only');
            END
            """
        )
    elif dialect == "postgresql":
        op.execute(
            """
            CREATE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
            BEGIN
              RAISE EXCEPTION 'audit_events is append-only';
            END;
            $$ LANGUAGE plpgsql
            """
        )
        op.execute(
            """
            CREATE TRIGGER audit_events_no_mutation
            BEFORE UPDATE OR DELETE ON audit_events
            FOR EACH ROW EXECUTE FUNCTION reject_audit_event_mutation()
            """
        )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "postgresql":
        op.execute("DROP TRIGGER audit_events_no_mutation ON audit_events")
        op.execute("DROP FUNCTION reject_audit_event_mutation()")
    op.drop_table("jobs")
    op.drop_table("audit_events")
