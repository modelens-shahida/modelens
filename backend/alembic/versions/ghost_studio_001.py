"""add ghost studio models

Revision ID: ghost_studio_001
Revises: architecture_v1_001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'ghost_studio_001'
down_revision = 'architecture_v1_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ghost_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, default='queued', index=True),
        sa.Column('product_hint', sa.Text(), nullable=True),
        sa.Column('garment_type', sa.String(100), nullable=True),
        sa.Column('view', sa.String(50), nullable=True),
        sa.Column('aspect_ratio', sa.String(20), nullable=True),
        sa.Column('resolution', sa.String(10), nullable=True),
        sa.Column('preserve_print', sa.Boolean(), nullable=False, default=True),
        sa.Column('preserve_seams', sa.Boolean(), nullable=False, default=True),
        sa.Column('generation_mode', sa.String(20), nullable=True),
        sa.Column('credits_reserved', sa.Integer(), nullable=False, default=0),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, default=0),
        sa.Column('progress', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'ghost_job_assets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ghost_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('mask_path', sa.String(500), nullable=True),
        sa.Column('crop_data', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'ghost_outputs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ghost_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('output_url', sa.String(500), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('fidelity_status', sa.String(50), nullable=True),
        sa.Column('api_interaction_id', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('ghost_outputs')
    op.drop_table('ghost_job_assets')
    op.drop_table('ghost_jobs')
