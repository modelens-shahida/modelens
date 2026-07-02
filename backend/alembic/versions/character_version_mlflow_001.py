"""add mlflow_run_id to character_versions

Revision ID: character_version_mlflow_001
Revises: webhook_logs_001
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa

revision = 'character_version_mlflow_001'
down_revision = 'webhook_logs_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('character_versions', sa.Column('mlflow_run_id', sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column('character_versions', 'mlflow_run_id')
