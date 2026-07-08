"""add domain_whitelist to brands

Revision ID: brand_sso_001
Revises: invitations_001
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'brand_sso_001'
down_revision = 'invitations_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('brands', sa.Column('domain_whitelist', JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column('brands', 'domain_whitelist')
