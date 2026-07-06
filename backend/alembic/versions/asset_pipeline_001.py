"""add image metadata and thumbnail columns to assets

Revision ID: asset_pipeline_001
Revises: brand_tier_001
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'asset_pipeline_001'
down_revision = 'brand_tier_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('assets', sa.Column('width', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('height', sa.Integer(), nullable=True))
    op.add_column('assets', sa.Column('aspect_ratio', sa.String(20), nullable=True))
    op.add_column('assets', sa.Column('thumbnail_url', sa.String(1000), nullable=True))
    op.add_column('assets', sa.Column('preview_url', sa.String(1000), nullable=True))


def downgrade() -> None:
    op.drop_column('assets', 'preview_url')
    op.drop_column('assets', 'thumbnail_url')
    op.drop_column('assets', 'aspect_ratio')
    op.drop_column('assets', 'height')
    op.drop_column('assets', 'width')
