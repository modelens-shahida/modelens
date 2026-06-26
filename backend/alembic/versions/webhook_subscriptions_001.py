"""add webhook_subscriptions table

Revision ID: webhook_subscriptions_001
Revises: schema_upgrades_v1
Create Date: 2026-06-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'webhook_subscriptions_001'
down_revision = 'schema_upgrades_v1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'webhook_subscriptions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('url', sa.String(1000), nullable=False),
        sa.Column('events', JSONB, nullable=False, server_default='[]'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('webhook_subscriptions')
