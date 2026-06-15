"""add_campaign_themes_table

Revision ID: 6b72a9e32f91
Revises: e2b34a9f939e
Create Date: 2026-06-15 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6b72a9e32f91'
down_revision: Union[str, Sequence[str], None] = 'e2b34a9f939e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'campaign_themes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('brand_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('theme_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.ForeignKeyConstraint(['brand_id'], ['brands.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_campaign_themes_brand_id', 'campaign_themes', ['brand_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_campaign_themes_brand_id', table_name='campaign_themes')
    op.drop_table('campaign_themes')
