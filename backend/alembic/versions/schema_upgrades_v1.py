"""schema upgrades v1 - character versions, embeddings, theme packages, generated videos, fix requests

Revision ID: schema_upgrades_v1
Revises: add_fk_indexes_001
Create Date: 2026-06-20

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'schema_upgrades_v1'
down_revision = 'add_fk_indexes_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. character_versions table
    op.create_table(
        'character_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('character_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_number', sa.Integer(), default=1),
        sa.Column('prompt_trigger', sa.Text(), nullable=True),
        sa.Column('reference_image_path', sa.String(1000), nullable=True),
        sa.Column('validation_image_path', sa.String(1000), nullable=True),
        sa.Column('config_overrides', JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 2. character_embeddings table
    op.create_table(
        'character_embeddings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('character_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version_id', sa.Integer(), sa.ForeignKey('character_versions.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('embedding', sa.Text(), nullable=True),
        sa.Column('tag', sa.String(255), nullable=False),
    )

    # 3. theme_packages table
    op.create_table(
        'theme_packages',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('theme_id', sa.Integer(), sa.ForeignKey('campaign_themes.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('character_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='SET NULL'), nullable=True),
        sa.Column('workflow_template_id', sa.Integer(), sa.ForeignKey('workflow_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('prompt_template_id', sa.Integer(), sa.ForeignKey('prompt_templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('location_name', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 4. generated_videos table
    op.create_table(
        'generated_videos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ai_jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('source_asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('storage_path', sa.String(1000), nullable=False),
        sa.Column('motion_type', sa.String(100), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), default=5),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 5. fix_requests table
    op.create_table(
        'fix_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('original_asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('job_id', sa.Integer(), sa.ForeignKey('ai_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('updated_asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('requester_notes', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('reviewer_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # 6. Add theme_id to campaigns table
    op.add_column('campaigns', sa.Column(
        'theme_id', sa.Integer(),
        sa.ForeignKey('campaign_themes.id', ondelete='SET NULL'),
        nullable=True
    ))

    # 7. Add index on assets.asset_type
    op.create_index('idx_assets_asset_type', 'assets', ['asset_type'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_assets_asset_type', table_name='assets')
    op.drop_column('campaigns', 'theme_id')
    op.drop_table('fix_requests')
    op.drop_table('generated_videos')
    op.drop_table('theme_packages')
    op.drop_table('character_embeddings')
    op.drop_table('character_versions')
