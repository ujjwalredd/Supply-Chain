"""Add agent monitoring tables

Revision ID: 008_agent_tables
Revises: 007
Create Date: 2026-03-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '008_agent_tables'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_heartbeats',
        sa.Column('agent_id', sa.String(60), primary_key=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='STARTING'),
        sa.Column('last_seen', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('current_task', sa.Text(), nullable=True),
        sa.Column('metrics', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('error_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('model', sa.String(80), nullable=True),
        sa.Column('uptime_seconds', sa.Integer(), nullable=True, server_default='0'),
    )
    op.create_table(
        'agent_audit_log',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('agent_id', sa.String(60), nullable=False),
        sa.Column('action', sa.String(120), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('outcome', sa.String(20), nullable=True),
        sa.Column('details', postgresql.JSONB(), nullable=True, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_table(
        'agent_corrections',
        sa.Column('id', sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column('from_agent', sa.String(60), nullable=False),
        sa.Column('to_agent', sa.String(60), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('applied', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    )
    op.create_index('ix_agent_audit_log_agent_id', 'agent_audit_log', ['agent_id'])
    op.create_index('ix_agent_audit_log_created_at', 'agent_audit_log', ['created_at'])
    op.create_index('ix_agent_corrections_to_agent', 'agent_corrections', ['to_agent', 'applied'])


def downgrade() -> None:
    op.drop_index('ix_agent_corrections_to_agent', table_name='agent_corrections')
    op.drop_index('ix_agent_audit_log_created_at', table_name='agent_audit_log')
    op.drop_index('ix_agent_audit_log_agent_id', table_name='agent_audit_log')
    op.drop_table('agent_corrections')
    op.drop_table('agent_audit_log')
    op.drop_table('agent_heartbeats')
