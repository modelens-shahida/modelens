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


def create_index_safe(index_name, table_name, columns, **kwargs):
    conn = op.get_bind()
    result = conn.execute(sa.text(f"SELECT 1 FROM pg_class WHERE relname = '{index_name}'"))
    if not result.scalar():
        op.create_index(index_name, table_name, columns, **kwargs)


def upgrade() -> None:
    """Upgrade schema."""
    create_index_safe('idx_brand_members_user_id', 'brand_members', ['user_id'])
    create_index_safe('idx_assets_brand_id', 'assets', ['brand_id'])
    create_index_safe('idx_ai_jobs_brand_id', 'ai_jobs', ['brand_id'])
    create_index_safe('idx_ai_jobs_user_id', 'ai_jobs', ['user_id'])
    create_index_safe('idx_characters_brand_id', 'characters', ['brand_id'])


def downgrade() -> None:
    """Downgrade schema."""
    # Safe drops
    conn = op.get_bind()
    for idx in ['idx_characters_brand_id', 'idx_ai_jobs_user_id', 'idx_ai_jobs_brand_id', 'idx_assets_brand_id', 'idx_brand_members_user_id']:
        result = conn.execute(sa.text(f"SELECT 1 FROM pg_class WHERE relname = '{idx}'"))
        if result.scalar():
            op.drop_index(idx)
