"""add webhook_logs table

Revision ID: webhook_logs_001
Revises: credit_transactions_001
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'webhook_logs_001'
down_revision = 'credit_transactions_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('subscription_id', sa.Integer(), sa.ForeignKey('webhook_subscriptions.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('event', sa.String(100), nullable=False, index=True),
        sa.Column('payload', JSONB, nullable=False, server_default='{}'),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('attempt', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('is_success', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('webhook_logs')
