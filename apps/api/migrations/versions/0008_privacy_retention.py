"""Allow age-limited, checkpointed audit prefix retirement; updates stay forbidden."""

import sqlalchemy as sa
from alembic import op

revision = "0008_privacy_retention"
down_revision = "0007_hash_only"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_checkpoint",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_hash", sa.String(71), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
        BEGIN
          IF TG_OP = 'DELETE' AND OLD.created_at <= CURRENT_TIMESTAMP - INTERVAL '30 days'
             AND EXISTS (SELECT 1 FROM audit_checkpoint WHERE id = 1 AND sequence >= OLD.sequence)
          THEN RETURN OLD; END IF;
          RAISE EXCEPTION 'audit_events is append-only outside checkpointed retention';
        END; $$ LANGUAGE plpgsql
        """)
    else:
        op.execute("DROP TRIGGER audit_events_no_delete")
        op.execute("""
        CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
        WHEN NOT (
          julianday(OLD.created_at) <= julianday('now', '-30 days') AND
          EXISTS (SELECT 1 FROM audit_checkpoint WHERE id = 1 AND sequence >= OLD.sequence)
        ) BEGIN
          SELECT RAISE(ABORT, 'audit_events is append-only outside checkpointed retention');
        END
        """)


def downgrade() -> None:
    if op.get_bind().execute(sa.text("SELECT COUNT(*) FROM audit_checkpoint")).scalar():
        raise RuntimeError("Cannot remove audit checkpoint after retention; roll forward instead")
    if op.get_bind().dialect.name == "postgresql":
        op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_event_mutation() RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'audit_events is append-only'; END; $$ LANGUAGE plpgsql
        """)
    else:
        op.execute("DROP TRIGGER audit_events_no_delete")
        op.execute("""
        CREATE TRIGGER audit_events_no_delete BEFORE DELETE ON audit_events
        BEGIN SELECT RAISE(ABORT, 'audit_events is append-only'); END
        """)
    op.drop_table("audit_checkpoint")
