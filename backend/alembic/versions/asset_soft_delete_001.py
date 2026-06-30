"""add soft delete to assets

Revision ID: asset_soft_delete_001
Revises: webhook_subscriptions_001
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa

revision = 'asset_soft_delete_001'
down_revision = 'webhook_subscriptions_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('status', sa.String(length=50), nullable=True))
    op.add_column('assets', sa.Column('deleted_at', sa.DateTime(), nullable=True))
    op.create_index('idx_assets_deleted_at', 'assets', ['deleted_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_assets_deleted_at', table_name='assets')
    op.drop_column('assets', 'deleted_at')
    op.drop_column('assets', 'status')
