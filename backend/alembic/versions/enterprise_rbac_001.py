"""add enterprise RBAC audit logs

Revision ID: enterprise_rbac_001
Revises: digital_asset_registry_001
Create Date: 2026-08-29

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'enterprise_rbac_001'
down_revision = 'digital_asset_registry_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'audit_logs_v2',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False, index=True),
        sa.Column('actor_user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('brand_id', sa.Integer(), sa.ForeignKey('brands.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('resource_type', sa.String(100), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('metadata', JSONB, nullable=True),
        sa.Column('ip_address', sa.String(50), nullable=True),
        sa.Column('severity', sa.String(20), nullable=False, server_default='INFO'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )


def downgrade() -> None:
    op.drop_table('audit_logs_v2')
