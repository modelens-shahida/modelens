"""add_performance_indexes

Revision ID: e2b34a9f939e
Revises: 1ee880cf2a30
Create Date: 2026-06-13 09:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b34a9f939e'
down_revision: Union[str, Sequence[str], None] = '1ee880cf2a30'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('idx_brand_members_user_id', 'brand_members', ['user_id'])
    op.create_index('idx_assets_brand_id', 'assets', ['brand_id'])
    op.create_index('idx_ai_jobs_brand_id', 'ai_jobs', ['brand_id'])
    op.create_index('idx_ai_jobs_user_id', 'ai_jobs', ['user_id'])
    op.create_index('idx_characters_brand_id', 'characters', ['brand_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_characters_brand_id', table_name='characters')
    op.drop_index('idx_ai_jobs_user_id', table_name='ai_jobs')
    op.drop_index('idx_ai_jobs_brand_id', table_name='ai_jobs')
    op.drop_index('idx_assets_brand_id', table_name='assets')
    op.drop_index('idx_brand_members_user_id', table_name='brand_members')
