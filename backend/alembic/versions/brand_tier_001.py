"""add tier and credit quota to brands

Revision ID: brand_tier_001
Revises: webhook_filtering_001
Create Date: 2026-07-05

"""
from alembic import op
import sqlalchemy as sa

revision = 'brand_tier_001'
down_revision = 'webhook_filtering_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('brands', sa.Column('tier', sa.String(50), nullable=False, server_default='free'))
    op.add_column('brands', sa.Column('monthly_credit_quota', sa.Integer(), nullable=False, server_default='100'))
    op.add_column('brands', sa.Column('credits_used_this_month', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('brands', sa.Column('tier_reset_at', sa.DateTime(), nullable=True))
    op.create_index('idx_brands_tier', 'brands', ['tier'])


def downgrade() -> None:
    op.drop_index('idx_brands_tier', table_name='brands')
    op.drop_column('brands', 'tier_reset_at')
    op.drop_column('brands', 'credits_used_this_month')
    op.drop_column('brands', 'monthly_credit_quota')
    op.drop_column('brands', 'tier')
