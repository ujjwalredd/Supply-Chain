"""Add indexes and outcome tracking columns to pending_actions.

Revision ID: 003
Revises: 002
Create Date: 2026-03-10
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # ------------------------------------------------------------------
    # Add outcome tracking columns to pending_actions
    # ------------------------------------------------------------------
    existing_cols = {col["name"] for col in inspector.get_columns("pending_actions")}

    if "resolved" not in existing_cols:
        op.add_column(
            "pending_actions",
            sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        )

    if "outcome_note" not in existing_cols:
        op.add_column(
            "pending_actions",
            sa.Column("outcome_note", sa.Text(), nullable=True),
        )

    if "resolved_at" not in existing_cols:
        op.add_column(
            "pending_actions",
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )

    # ------------------------------------------------------------------
    # Indexes
    # ------------------------------------------------------------------
    existing_indexes = {idx["name"] for idx in inspector.get_indexes("pending_actions")}
    if "ix_pending_actions_resolved" not in existing_indexes:
        op.create_index(
            "ix_pending_actions_resolved",
            "pending_actions",
            ["resolved"],
        )

    existing_dev_indexes = {idx["name"] for idx in inspector.get_indexes("deviations")}

    # Index on deviations(type, detected_at DESC) — useful for type-filtered time-range queries
    if "ix_deviations_type_detected_at" not in existing_dev_indexes:
        op.create_index(
            "ix_deviations_type_detected_at",
            "deviations",
            ["type", sa.text("detected_at DESC")],
        )

    # Index on deviations(severity, executed, detected_at DESC) — bulk triage queries
    if "ix_deviations_severity_executed_detected_at" not in existing_dev_indexes:
        op.create_index(
            "ix_deviations_severity_executed_detected_at",
            "deviations",
            ["severity", "executed", sa.text("detected_at DESC")],
        )

    existing_order_indexes = {idx["name"] for idx in inspector.get_indexes("orders")}

    # Index on orders(supplier_id, status) — supplier-scoped status filters
    if "ix_orders_supplier_id_status" not in existing_order_indexes:
        op.create_index(
            "ix_orders_supplier_id_status",
            "orders",
            ["supplier_id", "status"],
        )

    # Index on orders(expected_delivery) — delay prediction and overdue queries
    if "ix_orders_expected_delivery" not in existing_order_indexes:
        op.create_index(
            "ix_orders_expected_delivery",
            "orders",
            ["expected_delivery"],
        )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_orders_expected_delivery", table_name="orders")
    op.drop_index("ix_orders_supplier_id_status", table_name="orders")
    op.drop_index("ix_deviations_severity_executed_detected_at", table_name="deviations")
    op.drop_index("ix_deviations_type_detected_at", table_name="deviations")
    op.drop_index("ix_pending_actions_resolved", table_name="pending_actions")

    # Drop columns
    op.drop_column("pending_actions", "resolved_at")
    op.drop_column("pending_actions", "outcome_note")
    op.drop_column("pending_actions", "resolved")
