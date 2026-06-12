"""make_embedding_nullable

Revision ID: 1ee880cf2a30
Revises: 7c4b5e6e1a90
Create Date: 2026-06-12 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '1ee880cf2a30'
down_revision: Union[str, Sequence[str], None] = '7c4b5e6e1a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter embedding column to be nullable
    op.alter_column('asset_tags', 'embedding',
               existing_type=pgvector.sqlalchemy.Vector(dim=1536),
               nullable=True)


def downgrade() -> None:
    # Revert embedding column to NOT NULL
    op.alter_column('asset_tags', 'embedding',
               existing_type=pgvector.sqlalchemy.Vector(dim=1536),
               nullable=False)
