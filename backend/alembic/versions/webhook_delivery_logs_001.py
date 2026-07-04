"""add webhook_delivery_logs table

Revision ID: webhook_delivery_logs_001
Revises: notifications_001
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'webhook_delivery_logs_001'
down_revision = 'notifications_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_delivery_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('webhook_subscriptions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('payload', JSONB, nullable=False, server_default='{}'),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='success', index=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('webhook_delivery_logs')
