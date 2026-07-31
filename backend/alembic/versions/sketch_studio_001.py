"""add sketch studio models

Revision ID: sketch_studio_001
Revises: move_studio_001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'sketch_studio_001'
down_revision = 'move_studio_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'sketch_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('product_hint', sa.Text(), nullable=True),
        sa.Column('material_description', sa.Text(), nullable=True),
        sa.Column('model_brief', sa.Text(), nullable=True),
        sa.Column('background_brief', sa.Text(), nullable=True),
        sa.Column('output_mode', sa.String(50), nullable=True, server_default='ON_MODEL'),
        sa.Column('resolution', sa.String(10), nullable=True, server_default='2K'),
        sa.Column('aspect_ratio', sa.String(20), nullable=True, server_default='3:4'),
        sa.Column('generation_mode', sa.String(50), nullable=True, server_default='studio_quality'),
        sa.Column('credits_reserved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'sketch_job_references',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('sketch_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('image_path', sa.String(500), nullable=True),
        sa.Column('mask_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'sketch_outputs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('sketch_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('output_url', sa.String(500), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('api_interaction_id', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('sketch_outputs')
    op.drop_table('sketch_job_references')
    op.drop_table('sketch_jobs')
