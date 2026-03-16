"""Add unique constraint and index for order event sourcing

Revision ID: 009_add_event_sourcing_constraints
Revises: 008_agent_tables
Create Date: 2026-03-16 00:00:00.000000

NOTE: Uses conditional DDL (IF NOT EXISTS / DO $$ ... $$) so this migration
is idempotent.  If the database was initialised via SQLAlchemy create_all()
*after* models.py already declared the UniqueConstraint (e.g. a fresh
install), the constraint and index will already exist and this migration
will skip them cleanly rather than raising a DuplicateObject error.
"""
from alembic import op

revision = '009'
down_revision = '008_agent_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Unique constraint — wrap in PL/pgSQL block so we can check existence first.
    # pg_constraint stores constraint names in pg_catalog; conrelid scopes to the
    # exact table so there is no risk of a false-positive match from another table.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM   pg_constraint c
                JOIN   pg_class      t ON t.oid = c.conrelid
                WHERE  c.conname = 'uq_order_events_order_version'
                AND    t.relname = 'order_events'
            ) THEN
                ALTER TABLE order_events
                    ADD CONSTRAINT uq_order_events_order_version
                    UNIQUE (order_id, aggregate_version);
            END IF;
        END $$;
    """)

    # Index — CREATE INDEX IF NOT EXISTS is standard PostgreSQL syntax.
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_order_events_order_version
            ON order_events (order_id, aggregate_version);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_order_events_order_version")
    op.execute("""
        ALTER TABLE order_events
            DROP CONSTRAINT IF EXISTS uq_order_events_order_version
    """)
