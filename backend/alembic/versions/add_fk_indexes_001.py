"""add fk indexes

Revision ID: add_fk_indexes_001
Revises: e2b34a9f939e
Create Date: 2026-06-18

"""
from alembic import op

revision = 'add_fk_indexes_001'
down_revision = 'e2b34a9f939e'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('idx_assets_brand_id_fk', 'assets', ['brand_id'], unique=False)
    op.create_index('idx_brand_members_user_id_fk', 'brand_members', ['user_id'], unique=False)
    op.create_index('idx_ai_jobs_brand_id_fk', 'ai_jobs', ['brand_id'], unique=False)
    op.create_index('idx_ai_jobs_user_id_fk', 'ai_jobs', ['user_id'], unique=False)
    op.create_index('idx_characters_brand_id_fk', 'characters', ['brand_id'], unique=False)
    op.create_index('idx_prompt_templates_brand_id_fk', 'prompt_templates', ['brand_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_assets_brand_id_fk', table_name='assets')
    op.drop_index('idx_brand_members_user_id_fk', table_name='brand_members')
    op.drop_index('idx_ai_jobs_brand_id_fk', table_name='ai_jobs')
    op.drop_index('idx_ai_jobs_user_id_fk', table_name='ai_jobs')
    op.drop_index('idx_characters_brand_id_fk', table_name='characters')
    op.drop_index('idx_prompt_templates_brand_id_fk', table_name='prompt_templates')
