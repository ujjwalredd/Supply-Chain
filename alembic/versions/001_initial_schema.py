"""Initial schema: orders, suppliers, deviations, ontology_constraints.

Revision ID: 001
Revises:
Create Date: 2025-02-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("order_id", sa.String(64), primary_key=True),
        sa.Column("supplier_id", sa.String(32), nullable=False, index=True),
        sa.Column("product", sa.String(128), nullable=False, index=True),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Float(), nullable=False),
        sa.Column("order_value", sa.Float(), nullable=False),
        sa.Column("expected_delivery", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_delivery", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delay_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, index=True),
        sa.Column("inventory_level", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "suppliers",
        sa.Column("supplier_id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("region", sa.String(32), nullable=False),
        sa.Column("trust_score", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("total_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delayed_orders", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("avg_delay_days", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("contract_terms", postgresql.JSONB(), nullable=True),
        sa.Column("capacity_limits", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "deviations",
        sa.Column("deviation_id", sa.String(64), primary_key=True),
        sa.Column("order_id", sa.String(64), sa.ForeignKey("orders.order_id"), nullable=False, index=True),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ai_analysis", postgresql.JSONB(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "ontology_constraints",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("entity_id", sa.String(128), nullable=False, index=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("constraint_type", sa.String(64), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("hard_limit", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("ontology_constraints")
    op.drop_table("deviations")
    op.drop_table("suppliers")
    op.drop_table("orders")
