"""Add supplier_policies table for Glass-Box Autonomy feature.

Revision ID: 006
Revises: 005
Create Date: 2026-03-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "supplier_policies",
        sa.Column("supplier_id", sa.String(32), primary_key=True),
        sa.Column("require_approval_at_severity", sa.String(16), nullable=False, server_default="CRITICAL"),
        sa.Column("require_approval_above_value", sa.Float, nullable=False, server_default="50000.0"),
        sa.Column("max_auto_actions_per_day", sa.Integer, nullable=False, server_default="10"),
        sa.Column("min_confidence", sa.Float, nullable=False, server_default="0.70"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("supplier_policies")
