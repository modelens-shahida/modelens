"""add created_at to assets table

Revision ID: add_asset_created_at_001
Revises: asset_pipeline_001
Create Date: 2026-07-07

"""
from alembic import op
import sqlalchemy as sa

revision = 'add_asset_created_at_001'
down_revision = 'asset_pipeline_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()))


def downgrade() -> None:
    op.drop_column('assets', 'created_at')
