"""add taxonomy registry

Revision ID: taxonomy_registry_001
Revises: 28ccf604a016
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'taxonomy_registry_001'
down_revision = '28ccf604a016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'taxonomy_items',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('taxonomy_id', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('taxonomy_type', sa.String(50), nullable=False, index=True),
        sa.Column('family', sa.String(100), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('version', sa.String(20), nullable=True, server_default='1.0'),
        sa.Column('approval_status', sa.String(50), nullable=False, server_default='pending', index=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('recommended_for', JSONB, nullable=True),
        sa.Column('not_recommended_for', JSONB, nullable=True),
        sa.Column('configuration', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('taxonomy_items')
