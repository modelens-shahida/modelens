"""add credit_transactions table

Revision ID: credit_transactions_001
Revises: audit_logs_001
Create Date: 2026-06-27

"""
from alembic import op
import sqlalchemy as sa

revision = 'credit_transactions_001'
down_revision = 'audit_logs_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'credit_transactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('amount', sa.Integer(), nullable=False),
        sa.Column('transaction_type', sa.String(50), nullable=False, index=True),
        sa.Column('reference_type', sa.String(50), nullable=True),
        sa.Column('reference_id', sa.Integer(), nullable=True),
        sa.Column('balance_after', sa.Integer(), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('credit_transactions')
