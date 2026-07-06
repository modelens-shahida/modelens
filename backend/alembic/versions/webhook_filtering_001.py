"""add filter_rules and payload_format to webhook_subscriptions

Revision ID: webhook_filtering_001
Revises: webhook_delivery_logs_001
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'webhook_filtering_001'
down_revision = 'webhook_delivery_logs_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('webhook_subscriptions', sa.Column('filter_rules', JSONB, nullable=True))
    op.add_column('webhook_subscriptions', sa.Column('payload_format', sa.String(50), nullable=False, server_default='verbose'))


def downgrade() -> None:
    op.drop_column('webhook_subscriptions', 'filter_rules')
    op.drop_column('webhook_subscriptions', 'payload_format')
