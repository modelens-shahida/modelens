"""production dispatch - customer productions with their runtime profile snapshot

Creates ``productions``: a customer production request linked to its
``ai_jobs`` row, with the admin-only Runtime Character Profile snapshot and
an idempotency key unique per user. Credits stay in the existing
credit_transactions ledger (reference_id = production_id). Nothing here
touches character_registry_versions. Safe to run twice.

Revision ID: production_dispatch_001
Revises: pose_resolver_001
Create Date: 2026-10-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'production_dispatch_001'
down_revision = 'pose_resolver_001'
branch_labels = None
depends_on = None

TABLE = 'productions'


def upgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        return
    op.create_table(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('production_id', sa.String(40), unique=True, nullable=False),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('brand_id', sa.Integer, sa.ForeignKey('brands.id', ondelete='CASCADE'), nullable=False),
        sa.Column('ai_job_id', sa.Integer, sa.ForeignKey('ai_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('product_asset_id', sa.Integer, sa.ForeignKey('assets.id', ondelete='SET NULL'), nullable=True),
        sa.Column('idempotency_key', sa.String(255), nullable=True),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('product_type', sa.String(30), nullable=False),
        sa.Column('request', JSONB, nullable=False),
        sa.Column('runtime_profile', JSONB, nullable=False),
        sa.Column('estimated_credits', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'idempotency_key', name='uq_production_idempotency_key'),
    )
    op.create_index('ix_productions_user_id', TABLE, ['user_id'])
    op.create_index('ix_productions_brand_id', TABLE, ['brand_id'])
    op.create_index('ix_productions_ai_job_id', TABLE, ['ai_job_id'])


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
