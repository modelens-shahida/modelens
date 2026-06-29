"""add fk indexes

Revision ID: add_fk_indexes_001
Revises: e2b34a9f939e
Create Date: 2026-06-18

"""
from alembic import op

revision = 'add_fk_indexes_001'
down_revision = '6b72a9e32f91'
branch_labels = None
depends_on = None


import sqlalchemy as sa

def create_index_safe(index_name, table_name, columns, **kwargs):
    conn = op.get_bind()
    result = conn.execute(sa.text(f"SELECT 1 FROM pg_class WHERE relname = '{index_name}'"))
    if not result.scalar():
        op.create_index(index_name, table_name, columns, **kwargs)


def upgrade() -> None:
    create_index_safe('idx_assets_brand_id_fk', 'assets', ['brand_id'], unique=False)
    create_index_safe('idx_brand_members_user_id_fk', 'brand_members', ['user_id'], unique=False)
    create_index_safe('idx_ai_jobs_brand_id_fk', 'ai_jobs', ['brand_id'], unique=False)
    create_index_safe('idx_ai_jobs_user_id_fk', 'ai_jobs', ['user_id'], unique=False)
    create_index_safe('idx_characters_brand_id_fk', 'characters', ['brand_id'], unique=False)


def downgrade() -> None:
    conn = op.get_bind()
    for idx in ['idx_assets_brand_id_fk', 'idx_brand_members_user_id_fk', 'idx_ai_jobs_brand_id_fk', 'idx_ai_jobs_user_id_fk', 'idx_characters_brand_id_fk']:
        result = conn.execute(sa.text(f"SELECT 1 FROM pg_class WHERE relname = '{idx}'"))
        if result.scalar():
            op.drop_index(idx)
