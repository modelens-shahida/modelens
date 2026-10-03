"""character version registry - Character Core fields, LOCKED immutability, EE-F-002 V1.0 seed

Extends ``character_registry_versions`` (model ``CharacterRegistryVersion``).
No earlier migration creates that table (``character_registry_v2_001`` names
it ``character_versions``, which clashes with the legacy training table), so it
is created here if missing; otherwise only the missing columns are added.

Adds a PostgreSQL trigger that rejects UPDATE of Character Core fields and
DELETE on LOCKED rows, then seeds EE-F-002 V1.0 as LOCKED. Safe to run twice.

Revision ID: character_version_registry_001
Revises: character_registry_v2_001
Create Date: 2026-10-03
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'character_version_registry_001'
down_revision = 'character_registry_v2_001'
branch_labels = None
depends_on = None

TABLE = 'character_registry_versions'

def _new_columns():
    return [
        sa.Column('canonical_height_cm', sa.Float, nullable=True),
        sa.Column('stature', sa.String(30), nullable=True),
        sa.Column('body_archetype', sa.String(50), nullable=True),
        sa.Column('parent_version', sa.String(10), nullable=True),
    ]

CORE_FIELDS = (
    'character_id', 'version', 'status', 'locked', 'locked_at', 'locked_by',
    'canonical_height_cm', 'stature', 'body_archetype', 'parent_version',
    'taxonomy_version', 'dna_snapshot',
)

EE_F_002_V1 = {
    'character_id': 'EE-F-002',
    'version': '1.0',
    'status': 'LOCKED',
    'locked': True,
    'locked_by': 'SYSTEM_SEED',
    'canonical_height_cm': 178.0,
    'stature': 'TALL',
    'body_archetype': 'HIGH_FASHION_RUNWAY_SLIM',
    'release_notes': 'EE-F-002 Eliska Novak V1.0 Character Core lock.',
}

_core_changed = ' OR '.join(f'NEW.{f} IS DISTINCT FROM OLD.{f}' for f in CORE_FIELDS)

GUARD_FUNCTION = f"""
CREATE OR REPLACE FUNCTION character_registry_versions_guard() RETURNS trigger AS $$
BEGIN
    IF COALESCE(OLD.locked, false) OR OLD.status = 'LOCKED' THEN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Character % version % is LOCKED and cannot be deleted', OLD.character_id, OLD.version
                USING ERRCODE = 'check_violation';
        END IF;
        IF {_core_changed} THEN
            RAISE EXCEPTION 'Character % version % is LOCKED and cannot be modified', OLD.character_id, OLD.version
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


def _create_table():
    op.create_table(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),
        sa.Column('status', sa.String(30), server_default='DEVELOPMENT'),
        sa.Column('locked', sa.Boolean, server_default=sa.false()),
        sa.Column('locked_at', sa.DateTime, nullable=True),
        sa.Column('locked_by', sa.String(100), nullable=True),
        sa.Column('promoted_to_production', sa.Boolean, server_default=sa.false()),
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        sa.Column('taxonomy_version', sa.String(20), nullable=True),
        sa.Column('dna_snapshot', JSONB, nullable=True),
        sa.Column('qa_snapshot', JSONB, nullable=True),
        sa.Column('release_notes', sa.Text, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        *_new_columns(),
        sa.UniqueConstraint('character_id', 'version', name='uq_character_registry_version'),
    )
    op.create_index('ix_char_registry_versions_character_id', TABLE, ['character_id'])


def _seed_ee_f_002(bind):
    versions = sa.table(TABLE, *[sa.column(name) for name in (
        'character_id', 'version', 'status', 'locked', 'locked_at', 'locked_by',
        'canonical_height_cm', 'stature', 'body_archetype', 'release_notes',
    )])
    row = bind.execute(
        sa.text(f"SELECT locked, status FROM {TABLE} WHERE character_id = :c AND version = :v"),
        {'c': EE_F_002_V1['character_id'], 'v': EE_F_002_V1['version']},
    ).first()
    values = {**EE_F_002_V1, 'locked_at': datetime.utcnow()}

    if row is None:
        bind.execute(versions.insert().values(**values))
    elif not (row.locked or row.status == 'LOCKED'):
        # An unlocked 1.0 draft: complete it with the canonical values and lock it.
        bind.execute(
            versions.update()
            .where(versions.c.character_id == EE_F_002_V1['character_id'])
            .where(versions.c.version == EE_F_002_V1['version'])
            .values(**values)
        )
    # Already LOCKED: never touched.


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table(TABLE):
        _create_table()
    else:
        existing = {c['name'] for c in inspector.get_columns(TABLE)}
        for col in _new_columns():
            if col.name not in existing:
                op.add_column(TABLE, col)
        uniques = {u['name'] for u in inspector.get_unique_constraints(TABLE)}
        if 'uq_character_registry_version' not in uniques:
            op.create_unique_constraint('uq_character_registry_version', TABLE, ['character_id', 'version'])

    if bind.dialect.name == 'postgresql':
        op.execute(GUARD_FUNCTION)
        op.execute(f"DROP TRIGGER IF EXISTS trg_character_registry_versions_guard ON {TABLE}")
        op.execute(
            f"CREATE TRIGGER trg_character_registry_versions_guard "
            f"BEFORE UPDATE OR DELETE ON {TABLE} "
            f"FOR EACH ROW EXECUTE FUNCTION character_registry_versions_guard()"
        )

    _seed_ee_f_002(bind)


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(f"DROP TRIGGER IF EXISTS trg_character_registry_versions_guard ON {TABLE}")
        op.execute("DROP FUNCTION IF EXISTS character_registry_versions_guard()")
    # Columns and the seeded row are kept: dropping them would destroy LOCKED
    # Character Core data, which this registry exists to preserve.
