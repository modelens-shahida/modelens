"""add angle shots models

Revision ID: angle_shots_001
Revises: catalog_studio_001
Create Date: 2026-08-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'angle_shots_001'
down_revision = 'catalog_studio_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'angle_shots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('code', sa.String(100), nullable=True, unique=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('framing', sa.String(100), nullable=True),
        sa.Column('pose', sa.String(100), nullable=True),
        sa.Column('view_direction', sa.String(50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('reference_image_url', sa.String(500), nullable=True),
        sa.Column('pose_map_url', sa.String(500), nullable=True),
        sa.Column('camera_yaw', sa.Float(), nullable=True),
        sa.Column('camera_pitch', sa.Float(), nullable=True),
        sa.Column('focal_length_mm', sa.Float(), nullable=True),
        sa.Column('is_custom', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_premium', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_visible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('status', sa.String(50), nullable=False, server_default='active', index=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('prompt_template', sa.Text(), nullable=True),
        sa.Column('quality_rules', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'angle_shot_compatibilities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('angle_shot_id', sa.Integer(), sa.ForeignKey('angle_shots.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('product_type', sa.String(100), nullable=False),
        sa.Column('compatible', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('warning_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'angle_shot_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('angle_shot_id', sa.Integer(), sa.ForeignKey('angle_shots.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('configuration', JSONB, nullable=False, server_default='{}'),
        sa.Column('change_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'shoot_angle_shots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('shoot_id', sa.Integer(), sa.ForeignKey('campaigns.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('angle_shot_id', sa.Integer(), sa.ForeignKey('angle_shots.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('angle_shot_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('configuration', JSONB, nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(50), nullable=False, server_default='selected'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('shoot_angle_shots')
    op.drop_table('angle_shot_versions')
    op.drop_table('angle_shot_compatibilities')
    op.drop_table('angle_shots')
