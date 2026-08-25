"""add digital asset registry and QA tables

Revision ID: digital_asset_registry_001
Revises: taxonomy_registry_001
Create Date: 2026-08-25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'digital_asset_registry_001'
down_revision = 'taxonomy_registry_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'asset_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('storage_uri', sa.String(500), nullable=True),
        sa.Column('content_hash_sha256', sa.String(64), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('mime_type', sa.String(100), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'asset_relationships',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('source_asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('target_asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('relationship_type', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'reference_sets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('character_id', sa.Integer(), sa.ForeignKey('characters.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(50), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'reference_set_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('reference_set_id', sa.Integer(), sa.ForeignKey('reference_sets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('view_code', sa.String(100), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'qa_profiles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('qa_profile_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('workflow', sa.String(100), nullable=True),
        sa.Column('generation_mode', sa.String(50), nullable=True),
        sa.Column('dimensions', JSONB, nullable=True),
        sa.Column('overall_pass_threshold', sa.Float(), nullable=True, server_default='92.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'qa_evaluations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('qa_profile_id', sa.Integer(), sa.ForeignKey('qa_profiles.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=True),
        sa.Column('overall_score', sa.Float(), nullable=True),
        sa.Column('decision', sa.String(50), nullable=True),
        sa.Column('dimension_scores', JSONB, nullable=True),
        sa.Column('hard_gate_failures', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'qa_artifacts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('evaluation_id', sa.Integer(), sa.ForeignKey('qa_evaluations.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('artifact_code', sa.String(100), nullable=False),
        sa.Column('severity', sa.String(50), nullable=False, server_default='WARNING'),
        sa.Column('bbox_x', sa.Float(), nullable=True),
        sa.Column('bbox_y', sa.Float(), nullable=True),
        sa.Column('bbox_width', sa.Float(), nullable=True),
        sa.Column('bbox_height', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        'workflow_node_maps',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('workflow_id', sa.String(100), nullable=False, index=True),
        sa.Column('taxonomy_type', sa.String(50), nullable=False),
        sa.Column('taxonomy_id', sa.String(100), nullable=False),
        sa.Column('node_id', sa.String(50), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('value_mapping', JSONB, nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('workflow_node_maps')
    op.drop_table('qa_artifacts')
    op.drop_table('qa_evaluations')
    op.drop_table('qa_profiles')
    op.drop_table('reference_set_items')
    op.drop_table('reference_sets')
    op.drop_table('asset_relationships')
    op.drop_table('asset_versions')
