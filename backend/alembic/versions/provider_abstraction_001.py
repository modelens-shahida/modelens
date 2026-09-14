"""provider abstraction - Provider, ProviderModel, ProviderRoute, RoutingPolicy

Revision ID: provider_abstraction_001
Revises: character_registry_001
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'provider_abstraction_001'
down_revision = 'character_registry_001'
branch_labels = None
depends_on = None


def upgrade():
    # Provider table
    op.create_table('providers',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('provider_id', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('provider_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(30), default='ACTIVE'),
        sa.Column('capabilities', JSONB, nullable=True),
        sa.Column('latency_profile', sa.String(20), nullable=True),
        sa.Column('cost_profile', sa.String(20), nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Provider Model table
    op.create_table('provider_models',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('model_id', sa.String(50), unique=True, nullable=False),
        sa.Column('provider_id', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('model_type', sa.String(50), nullable=True),
        sa.Column('status', sa.String(30), default='ACTIVE'),
        sa.Column('capabilities', JSONB, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_provider_models_provider_id', 'provider_models', ['provider_id'])

    # Provider Route table
    op.create_table('provider_routes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('route_id', sa.String(50), unique=True, nullable=False),
        sa.Column('workflow_id', sa.String(50), nullable=False),
        sa.Column('quality_mode', sa.String(30), nullable=False),
        sa.Column('provider_id', sa.String(50), nullable=False),
        sa.Column('model_id', sa.String(50), nullable=True),
        sa.Column('priority', sa.Integer, default=1),
        sa.Column('status', sa.String(30), default='ACTIVE'),
        sa.Column('fallback_route_id', sa.String(50), nullable=True),
        sa.Column('avg_latency_ms', sa.Integer, nullable=True),
        sa.Column('avg_qa_score', sa.Float, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_provider_routes_workflow', 'provider_routes', ['workflow_id', 'quality_mode'])

    # Routing Policy table
    op.create_table('routing_policies',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('policy_id', sa.String(50), unique=True, nullable=False),
        sa.Column('workflow_id', sa.String(50), nullable=False),
        sa.Column('quality_mode', sa.String(30), nullable=False),
        sa.Column('primary_route_id', sa.String(50), nullable=False),
        sa.Column('fallback_route_id', sa.String(50), nullable=True),
        sa.Column('fallback_class', sa.String(30), default='FALLBACK-EQUIVALENT'),
        sa.Column('rules', JSONB, nullable=True),
        sa.Column('status', sa.String(30), default='ACTIVE'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_routing_policies_workflow', 'routing_policies', ['workflow_id', 'quality_mode'])


def downgrade():
    op.drop_table('routing_policies')
    op.drop_table('provider_routes')
    op.drop_table('provider_models')
    op.drop_table('providers')
