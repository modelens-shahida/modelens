"""appearance options - styling options layered on a Character Version; seed EE-F-002 V1.0 canonical look

Creates ``appearance_options`` with at most one default per character version
and category (partial unique index), then seeds the EE-F-002 V1.0 canonical
look (hair CANONICAL, makeup NATURAL, expression NEUTRAL_EDITORIAL) as
PRODUCTION defaults. Nothing here touches character_registry_versions.
Safe to run twice.

Revision ID: appearance_options_001
Revises: training_registry_001
Create Date: 2026-10-03
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'appearance_options_001'
down_revision = 'training_registry_001'
branch_labels = None
depends_on = None

TABLE = 'appearance_options'

SEED = (
    ('HAIR_STYLE', 'HAIR', 'CANONICAL', 'Canonical Straight', 'Sleek natural center-part editorial straight.'),
    ('MAKEUP_STYLE', 'MAKEUP', 'NATURAL', 'Natural Minimal', 'Clean bare-skin finish with subtle hydration.'),
    ('EXPRESSION', 'EXPRESSION', 'NEUTRAL_EDITORIAL', 'Neutral Editorial', 'High-fashion, poised and confident.'),
)


def _create_table():
    op.create_table(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('internal_key', sa.String(120), unique=True, nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('category', sa.String(30), nullable=False),
        sa.Column('option_id', sa.String(50), nullable=False),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='IN_DEVELOPMENT'),
        sa.Column('adapter_id', sa.String(50), nullable=True),
        sa.Column('validation', JSONB, nullable=True),
        sa.Column('compatibility_notes', sa.Text, nullable=True),
        sa.Column('qa_rules', JSONB, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('status_changed_by', sa.String(100), nullable=True),
        sa.Column('status_changed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('character_id', 'character_version', 'category', 'option_id', 'version',
                            name='uq_appearance_option_version'),
    )
    op.create_index('ix_appearance_options_character_id', TABLE, ['character_id'])
    op.create_index('uq_appearance_option_default', TABLE, ['character_id', 'character_version', 'category'],
                    unique=True, postgresql_where=sa.text('is_default'))


def _seed(bind):
    options = sa.table(TABLE, *[sa.column(c) for c in (
        'internal_key', 'character_id', 'character_version', 'category', 'option_id', 'version', 'label',
        'description', 'is_default', 'sort_order', 'status', 'compatibility_notes', 'created_by',
        'status_changed_by', 'status_changed_at',
    )])
    for category, segment, option_id, label, description in SEED:
        key = f"EE-F-002_{segment}_{option_id.replace('_', '-')}_V1"
        if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} WHERE internal_key = :k"), {'k': key}).first():
            continue
        has_default = bind.execute(sa.text(
            f"SELECT 1 FROM {TABLE} WHERE character_id = 'EE-F-002' AND character_version = '1.0' "
            "AND category = :c AND is_default"
        ), {'c': category}).first()
        bind.execute(options.insert().values(
            internal_key=key, character_id='EE-F-002', character_version='1.0', category=category,
            option_id=option_id, version=1, label=label, description=description,
            is_default=has_default is None, sort_order=0, status='PRODUCTION',
            compatibility_notes='Canonical V1.0 look, part of the EE-F-002 Character Core lock.',
            created_by='SYSTEM_SEED', status_changed_by='SYSTEM_SEED', status_changed_at=datetime.utcnow(),
        ))


def upgrade():
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(TABLE):
        _create_table()
    _seed(bind)


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
