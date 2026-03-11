"""Add composite indexes for common query patterns.

Revision ID: 005
Revises: 004
Create Date: 2026-03-11

Indexes added:
  orders:     (supplier_id, status)   — list_alerts JOIN + cost_analytics filters
              (supplier_id, created_at) — scorecard weekly queries
  deviations: severity                — alert list filtering by severity
              detected_at             — trend/cluster time-window queries
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_orders_supplier_status",  "orders",     ["supplier_id", "status"]),
    ("ix_orders_supplier_created", "orders",     ["supplier_id", "created_at"]),
    ("ix_deviations_severity",     "deviations", ["severity"]),
    ("ix_deviations_detected_at",  "deviations", ["detected_at"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Build set of existing index names per table so we skip already-created indexes
    existing: dict[str, set[str]] = {}
    for _, table, _ in _INDEXES:
        if table not in existing:
            existing[table] = {idx["name"] for idx in inspector.get_indexes(table)}

    for idx_name, table, columns in _INDEXES:
        if idx_name not in existing[table]:
            op.create_index(idx_name, table, columns)


def downgrade() -> None:
    for idx_name, table, _ in _INDEXES:
        op.drop_index(idx_name, table_name=table)
