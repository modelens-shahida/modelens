"""Add asset metadata and indices

Revision ID: f7e10e0045c1
Revises: 0aea3afd714b
Create Date: 2026-06-10 10:59:44.662156

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f7e10e0045c1'
down_revision: Union[str, Sequence[str], None] = '0aea3afd714b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add name and metadata (JSONB) columns to assets table
    op.add_column('assets', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column(
        'assets', 
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}')
    )

    # 2. Create GIN index on assets.metadata JSONB
    op.create_index('idx_assets_metadata_gin', 'assets', ['metadata'], postgresql_using='gin')

    # 3. Create functional FTS index on assets.name + metadata
    op.create_index(
        'idx_assets_name_metadata_fts',
        'assets',
        [sa.text("to_tsvector('english', coalesce(name, '') || ' ' || coalesce(metadata::text, ''))")],
        postgresql_using='gin'
    )

    # 4. Create IVFFlat index on asset_tags.embedding
    op.create_index(
        'idx_asset_tags_embedding_ivfflat',
        'asset_tags',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_with={'lists': 100},
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop indices
    op.drop_index('idx_asset_tags_embedding_ivfflat', table_name='asset_tags')
    op.drop_index('idx_assets_name_metadata_fts', table_name='assets')
    op.drop_index('idx_assets_metadata_gin', table_name='assets')

    # 2. Drop columns
    op.drop_column('assets', 'metadata')
    op.drop_column('assets', 'name')
