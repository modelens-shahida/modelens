"""runtime profiles: the approved, versioned way to run one character version

Creates ``runtime_profiles`` (DRAFT -> PRODUCTION -> RETIRED, one PRODUCTION
profile per character version via a partial unique index) as in
docs/character-runtime/APPEARANCE_STATUS.md 1.3 (PR AC-1): default and
allowed strategies, the pinned reference set, the adapter with its strength
and stronger fallback (CHECK 0 < strength <= 1 and strength < fallback <= 1),
the QA profile and the automatic-retry policy (default off).

Schema only: no data is written. Adapter strengths are data on these rows;
``EE-F-002_V1.0_RT_V1`` is created as DRAFT by an admin seed action
(POST /api/v1/admin/characters/EE-F-002/runtime-profiles/seed), never by a
migration. ``model_artifacts`` gains no columns: EVALUATION joins its status
vocabulary in code. Additive and safe to run twice: the table goes through
``create_table_if_absent`` and each index is created only when missing.
Freezing is enforced by ORM rules (app/models/db.py).

Revision ID: runtime_profiles_001
Revises: reference_sets_001
Create Date: 2026-10-23
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.migration_guard import create_table_if_absent

revision = 'runtime_profiles_001'
down_revision = 'reference_sets_001'
branch_labels = None
depends_on = None

TABLE = 'runtime_profiles'
PRODUCTION_ONLY = "status = 'PRODUCTION'"


def _jsonb():
    return sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def upgrade():
    create_table_if_absent(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('runtime_profile_id', sa.String(60), nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='DRAFT'),
        sa.Column('default_strategy', sa.String(30), nullable=False, server_default='REFERENCE_ONLY'),
        sa.Column('allowed_strategies', _jsonb(), nullable=False),
        sa.Column('reference_set_id', sa.Integer,
                  sa.ForeignKey('character_reference_sets.id', ondelete='RESTRICT'), nullable=True),
        sa.Column('adapter_id', sa.String(50), nullable=True),
        sa.Column('adapter_strength', sa.Float, nullable=True),
        sa.Column('fallback_adapter_strength', sa.Float, nullable=True),
        sa.Column('qa_profile_id', sa.String(100), nullable=True),
        sa.Column('fallback_retry_enabled', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('promoted_by', sa.String(100), nullable=True),
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        sa.Column('retired_by', sa.String(100), nullable=True),
        sa.Column('retired_at', sa.DateTime, nullable=True),
        sa.Column('retire_reason', sa.Text, nullable=True),
        sa.UniqueConstraint('runtime_profile_id', name='uq_runtime_profiles_runtime_profile_id'),
        sa.UniqueConstraint('character_id', 'character_version', 'version', name='uq_runtime_profile_version'),
        sa.CheckConstraint('adapter_strength > 0 AND adapter_strength <= 1', name='ck_runtime_profile_strength'),
        sa.CheckConstraint('fallback_adapter_strength > adapter_strength AND fallback_adapter_strength <= 1',
                           name='ck_runtime_profile_fallback_strength'),
    )
    existing = {ix['name'] for ix in sa.inspect(op.get_bind()).get_indexes(TABLE)}
    if 'ix_runtime_profiles_character_id' not in existing:
        op.create_index('ix_runtime_profiles_character_id', TABLE, ['character_id'])
    if 'uq_runtime_profile_production' not in existing:
        op.create_index('uq_runtime_profile_production', TABLE, ['character_id', 'character_version'], unique=True,
                        postgresql_where=sa.text(PRODUCTION_ONLY), sqlite_where=sa.text(PRODUCTION_ONLY))


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
