"""Add composite indexes on deviations for alert-list and type filter queries.

Revision ID: 007
Revises: 006
Create Date: 2026-03-12

Indexes added:
  deviations: (severity, executed)  — GET /alerts/enriched filters both cols on every call
              (type)                — GET /alerts?type=DELAY has no index today
              (order_id, executed)  — order timeline deviation lookup (executed=false)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_deviations_severity_executed", "deviations", ["severity", "executed"]),
    ("ix_deviations_type",              "deviations", ["type"]),
    ("ix_deviations_order_executed",    "deviations", ["order_id", "executed"]),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {idx["name"] for idx in inspector.get_indexes("deviations")}
    for idx_name, table, columns in _INDEXES:
        if idx_name not in existing:
            op.create_index(idx_name, table, columns)


def downgrade() -> None:
    for idx_name, table, _ in _INDEXES:
        op.drop_index(idx_name, table_name=table)
