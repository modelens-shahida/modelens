"""add invitations table

Revision ID: add_invitations_table
Revises: add_asset_created_at_001
Create Date: 2026-07-08

"""
from alembic import op
import sqlalchemy as sa


revision = 'add_invitations_table'
down_revision = 'add_asset_created_at_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'invitations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False, index=True),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('token', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('accepted_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('invitations')
