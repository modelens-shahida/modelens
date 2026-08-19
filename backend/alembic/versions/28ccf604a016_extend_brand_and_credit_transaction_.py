"""'extend_brand_and_credit_transaction_models'

Revision ID: 28ccf604a016
Revises: fluid_studio_001
Create Date: 2026-08-19 10:39:43.987099

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '28ccf604a016'
down_revision: Union[str, Sequence[str], None] = 'fluid_studio_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('brands', sa.Column('credits', sa.Integer(), nullable=False, server_default='100'))
    
    with op.batch_alter_table('credit_transactions') as batch_op:
        batch_op.add_column(sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=50), nullable=True, server_default='completed'))
        batch_op.create_index('ix_credit_transactions_brand_id', ['brand_id'])
        batch_op.alter_column('reference_id', type_=sa.String(length=255), existing_type=sa.Integer(), existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('credit_transactions') as batch_op:
        batch_op.drop_index('ix_credit_transactions_brand_id')
        batch_op.drop_column('status')
        batch_op.drop_column('brand_id')
        batch_op.alter_column('reference_id', type_=sa.Integer(), existing_type=sa.String(length=255), existing_nullable=True)
        
    op.drop_column('brands', 'credits')
