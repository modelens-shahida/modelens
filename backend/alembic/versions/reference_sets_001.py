"""reference sets: immutable, hashed sets of a character version's canonical assets

Creates ``character_reference_sets`` (DRAFT -> LOCKED -> PRODUCTION -> RETIRED,
one PRODUCTION set per character version via a partial unique index) and
``character_reference_set_items`` (canonical asset, role, order, the asset's
sha256 copied at lock) as in docs/character-runtime/DESIGN.md 3.1, plus the
``promoted_*`` / ``retired_*`` / ``created_by`` columns of the admin trail.

Schema only: no data is written. The EE-F-002 V1 set is built by an admin seed
action (POST /api/v1/admin/characters/EE-F-002/reference-sets/seed), never by
a migration. Additive and safe to run twice: each table goes through
``create_table_if_absent`` and each index is created only when missing.
Immutability is enforced by ORM rules (app/models/db.py) and re-checked by
hash when a set is resolved.

Revision ID: reference_sets_001
Revises: capability_validations_002
Create Date: 2026-10-21
"""
from alembic import op
import sqlalchemy as sa

from app.migration_guard import create_table_if_absent

revision = 'reference_sets_001'
down_revision = 'capability_validations_002'
branch_labels = None
depends_on = None

SETS = 'character_reference_sets'
ITEMS = 'character_reference_set_items'
PRODUCTION_ONLY = "status = 'PRODUCTION'"


def _indexes(bind, table):
    return {ix['name'] for ix in sa.inspect(bind).get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    create_table_if_absent(SETS,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('reference_set_id', sa.String(60), nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='DRAFT'),
        sa.Column('content_hash', sa.String(64), nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('locked_at', sa.DateTime, nullable=True),
        sa.Column('locked_by', sa.String(100), nullable=True),
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        sa.Column('promoted_by', sa.String(100), nullable=True),
        sa.Column('retired_at', sa.DateTime, nullable=True),
        sa.Column('retired_by', sa.String(100), nullable=True),
        sa.Column('retire_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('reference_set_id', name='uq_character_reference_sets_reference_set_id'),
        sa.UniqueConstraint('character_id', 'character_version', 'version', name='uq_reference_set_version'),
    )
    existing = _indexes(bind, SETS)
    if 'ix_character_reference_sets_character_id' not in existing:
        op.create_index('ix_character_reference_sets_character_id', SETS, ['character_id'])
    if 'uq_reference_set_production' not in existing:
        op.create_index('uq_reference_set_production', SETS, ['character_id', 'character_version'], unique=True,
                        postgresql_where=sa.text(PRODUCTION_ONLY), sqlite_where=sa.text(PRODUCTION_ONLY))

    create_table_if_absent(ITEMS,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('reference_set_id', sa.Integer, sa.ForeignKey(f'{SETS}.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('canonical_asset_id', sa.Integer, sa.ForeignKey('canonical_assets.id', ondelete='RESTRICT'),
                  nullable=False),
        sa.Column('asset_id', sa.String(50), nullable=False),
        sa.Column('role', sa.String(30), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('content_hash_sha256', sa.String(64), nullable=True),
        sa.UniqueConstraint('reference_set_id', 'role', 'sort_order', name='uq_reference_set_item_slot'),
        sa.UniqueConstraint('reference_set_id', 'canonical_asset_id', name='uq_reference_set_item_asset'),
    )
    existing = _indexes(bind, ITEMS)
    for column in ('reference_set_id', 'canonical_asset_id'):
        name = f'ix_character_reference_set_items_{column}'
        if name not in existing:
            op.create_index(name, ITEMS, [column])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in (ITEMS, SETS):
        if inspector.has_table(table):
            op.drop_table(table)
