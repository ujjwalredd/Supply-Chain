"""Add confidence column to pending_actions.

Revision ID: 004
Revises: 003
Create Date: 2026-03-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_cols = {col["name"] for col in inspector.get_columns("pending_actions")}
    if "confidence" not in existing_cols:
        op.add_column(
            "pending_actions",
            sa.Column("confidence", sa.Float(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("pending_actions", "confidence")
