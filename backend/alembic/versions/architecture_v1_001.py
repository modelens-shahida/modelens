"""add campaign_templates and editorial_assets tables

Revision ID: architecture_v1_001
Revises: brand_sso_001
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'architecture_v1_001'
down_revision = 'brand_sso_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'campaign_templates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('default_config', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'editorial_assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, unique=True, index=True),
        sa.Column('shot_type', sa.String(100), nullable=True),
        sa.Column('camera_body', sa.String(200), nullable=True),
        sa.Column('lens_spec', sa.String(200), nullable=True),
        sa.Column('lighting_setup', sa.String(200), nullable=True),
        sa.Column('composition_grid', sa.String(100), nullable=True),
        sa.Column('style_mood', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('editorial_assets')
    op.drop_table('campaign_templates')
