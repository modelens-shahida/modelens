"""add catalog studio models

Revision ID: catalog_studio_001
Revises: sketch_studio_001
Create Date: 2026-07-28

"""
from alembic import op
import sqlalchemy as sa

revision = 'catalog_studio_001'
down_revision = 'sketch_studio_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'catalog_jobs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('engine_mode', sa.String(50), nullable=True, server_default='product_to_model'),
        sa.Column('generation_mode', sa.String(50), nullable=True, server_default='studio_quality'),
        sa.Column('model_identity', sa.String(100), nullable=True),
        sa.Column('pose', sa.String(100), nullable=True),
        sa.Column('background', sa.String(100), nullable=True),
        sa.Column('aspect_ratio', sa.String(20), nullable=True, server_default='4:5'),
        sa.Column('resolution', sa.String(10), nullable=True, server_default='2K'),
        sa.Column('total_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_items', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('credits_reserved', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('credits_consumed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'catalog_job_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('catalog_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('sku_tag', sa.String(100), nullable=True),
        sa.Column('product_image_path', sa.String(500), nullable=True),
        sa.Column('mask_path', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued', index=True),
        sa.Column('output_url', sa.String(500), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('fidelity_status', sa.String(50), nullable=True),
        sa.Column('provider_job_id', sa.String(200), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


    op.create_table(
        'catalog_outputs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('catalog_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_item_id', sa.Integer(), sa.ForeignKey('catalog_job_items.id', ondelete='SET NULL'), nullable=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('output_url', sa.String(500), nullable=True),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('api_interaction_id', sa.String(200), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('catalog_outputs')
    op.drop_table('catalog_job_items')
    op.drop_table('catalog_jobs')
