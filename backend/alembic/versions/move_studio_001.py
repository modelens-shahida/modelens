"""add move studio video models

Revision ID: move_studio_001
Revises: ghost_studio_001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'move_studio_001'
down_revision = 'ghost_studio_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'video_projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('master_prompt', sa.Text(), nullable=True),
        sa.Column('aspect_ratio', sa.String(20), nullable=True, server_default='16:9'),
        sa.Column('mode', sa.String(50), nullable=True, server_default='standard'),
        sa.Column('status', sa.String(50), nullable=False, server_default='draft', index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'video_clips',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('video_projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('motion_preset', sa.String(100), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True, server_default='4.0'),
        sa.Column('start_image_url', sa.String(500), nullable=True),
        sa.Column('end_image_url', sa.String(500), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('provider_job_id', sa.String(200), nullable=True),
        sa.Column('clip_url', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('trim_start', sa.Float(), nullable=True),
        sa.Column('trim_end', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'video_renders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('video_projects.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('output_url', sa.String(500), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('resolution', sa.String(20), nullable=True, server_default='1080p'),
        sa.Column('audio_url', sa.String(500), nullable=True),
        sa.Column('logo_url', sa.String(500), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('video_renders')
    op.drop_table('video_clips')
    op.drop_table('video_projects')
