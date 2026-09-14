"""workspace isolation - add workspace_id to all entities

Revision ID: workspace_isolation_001
Revises: enterprise_rbac_001
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa

revision = 'workspace_isolation_001'
down_revision = 'enterprise_rbac_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add workspace_id to assets
    op.add_column('assets', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_assets_workspace_id', 'assets', ['workspace_id'])

    # Add workspace_id to catalog_jobs
    op.add_column('catalog_jobs', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_catalog_jobs_workspace_id', 'catalog_jobs', ['workspace_id'])

    # Add workspace_id to ghost_jobs
    op.add_column('ghost_jobs', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_ghost_jobs_workspace_id', 'ghost_jobs', ['workspace_id'])

    # Add workspace_id to sketch_jobs
    op.add_column('sketch_jobs', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_sketch_jobs_workspace_id', 'sketch_jobs', ['workspace_id'])

    # Add workspace_id to video_projects
    op.add_column('video_projects', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_video_projects_workspace_id', 'video_projects', ['workspace_id'])

    # Add workspace_id to reference_sets
    op.add_column('reference_sets', sa.Column('workspace_id', sa.String(50), nullable=True))

    # Add workspace_id to qa_evaluations
    op.add_column('qa_evaluations', sa.Column('workspace_id', sa.String(50), nullable=True))

    # Add workspace_id to audit_logs_v2
    op.add_column('audit_logs_v2', sa.Column('workspace_id', sa.String(50), nullable=True))
    op.create_index('ix_audit_logs_workspace_id', 'audit_logs_v2', ['workspace_id'])


def downgrade():
    op.drop_index('ix_assets_workspace_id', 'assets')
    op.drop_column('assets', 'workspace_id')

    op.drop_index('ix_catalog_jobs_workspace_id', 'catalog_jobs')
    op.drop_column('catalog_jobs', 'workspace_id')

    op.drop_index('ix_ghost_jobs_workspace_id', 'ghost_jobs')
    op.drop_column('ghost_jobs', 'workspace_id')

    op.drop_index('ix_sketch_jobs_workspace_id', 'sketch_jobs')
    op.drop_column('sketch_jobs', 'workspace_id')

    op.drop_index('ix_video_projects_workspace_id', 'video_projects')
    op.drop_column('video_projects', 'workspace_id')

    op.drop_column('reference_sets', 'workspace_id')
    op.drop_column('qa_evaluations', 'workspace_id')

    op.drop_index('ix_audit_logs_workspace_id', 'audit_logs_v2')
    op.drop_column('audit_logs_v2', 'workspace_id')
