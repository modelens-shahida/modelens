"""immutable credit ledger - add hash chaining to credit transactions

Revision ID: credit_ledger_001
Revises: pose_geometry_separation_001
Create Date: 2026-09-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'credit_ledger_001'
down_revision = 'pose_geometry_separation_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add hash chaining fields to credit_transactions
    op.add_column('credit_transactions',
        sa.Column('chain_hash', sa.String(64), nullable=True))
    op.add_column('credit_transactions',
        sa.Column('previous_hash', sa.String(64), nullable=True))
    op.add_column('credit_transactions',
        sa.Column('balance_after', sa.Integer, nullable=True))

    op.create_index('ix_credit_transactions_chain_hash',
        'credit_transactions', ['chain_hash'])

    # Preservation profiles table
    op.create_table('preservation_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('profile_id', sa.String(50), unique=True, nullable=False),
        sa.Column('brand_id', sa.Integer, nullable=False),
        sa.Column('product_id', sa.String(50), nullable=True),
        sa.Column('profile_type', sa.String(30), nullable=False),
        sa.Column('constraints', JSONB, nullable=True),
        sa.Column('protection_zones', JSONB, nullable=True),
        sa.Column('workflow_params', JSONB, nullable=True),
        sa.Column('status', sa.String(30), default='ACTIVE'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_preservation_profiles_brand', 'preservation_profiles', ['brand_id'])
    op.create_index('ix_preservation_profiles_product', 'preservation_profiles', ['product_id'])


def downgrade():
    op.drop_index('ix_credit_transactions_chain_hash', 'credit_transactions')
    op.drop_column('credit_transactions', 'chain_hash')
    op.drop_column('credit_transactions', 'previous_hash')
    op.drop_column('credit_transactions', 'balance_after')
    op.drop_table('preservation_profiles')
