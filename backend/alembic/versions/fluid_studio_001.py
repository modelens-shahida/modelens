"""add fluid studio tables

Revision ID: fluid_studio_001
Revises: angle_shots_001
Create Date: 2026-08-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'fluid_studio_001'
down_revision = 'angle_shots_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. brand_models
    op.create_table(
        'brand_models',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('workspace_id', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('gender', sa.String(50), nullable=False, server_default='Female'),
        sa.Column('full_body_reference_asset_id', sa.String(100), nullable=False),
        sa.Column('portrait_reference_asset_id', sa.String(100), nullable=False),
        sa.Column('appearance_prompt', sa.Text(), nullable=True),
        sa.Column('rights_confirmed', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('workspace_id', 'name', name='uq_brand_model_workspace_name')
    )

    # 2. fluid_sessions
    op.create_table(
        'fluid_sessions',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False, index=True),
        sa.Column('workspace_id', sa.String(100), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False, server_default='model_01'),
        sa.Column('model_prompt', sa.Text(), nullable=True),
        sa.Column('scene_prompt', sa.Text(), nullable=True),
        sa.Column('pose_reference_asset_id', sa.String(100), nullable=True),
        sa.Column('background_asset_id', sa.String(100), nullable=True),
        sa.Column('product_ids', JSONB, nullable=False, server_default='[]'),
        sa.Column('aspect_ratio', sa.String(20), nullable=False, server_default='4:5'),
        sa.Column('resolution', sa.String(20), nullable=False, server_default='2K'),
        sa.Column('generation_mode', sa.String(50), nullable=False, server_default='QUALITY'),
        sa.Column('active_layer_id', sa.String(50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 3. fluid_layers
    op.create_table(
        'fluid_layers',
        sa.Column('id', sa.String(50), primary_key=True),
        sa.Column('session_id', sa.String(50), sa.ForeignKey('fluid_sessions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('parent_layer_id', sa.String(50), nullable=True),
        sa.Column('operation', sa.String(100), nullable=False),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('provider_model', sa.String(100), nullable=False),
        sa.Column('provider_job_id', sa.String(100), nullable=False),
        sa.Column('image_url', sa.String(1000), nullable=False),
        sa.Column('mask_url', sa.String(1000), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('aspect_ratio', sa.String(20), nullable=False),
        sa.Column('quality_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('fluid_layers')
    op.drop_table('fluid_sessions')
    op.drop_table('brand_models')
