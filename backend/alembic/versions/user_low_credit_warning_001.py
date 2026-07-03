"""add last_low_credit_warning_at to users

Revision ID: user_low_credit_warning_001
Revises: webhook_secret_token_001
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa

revision = 'user_low_credit_warning_001'
down_revision = 'webhook_secret_token_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_low_credit_warning_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'last_low_credit_warning_at')
