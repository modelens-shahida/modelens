"""capability validations: per-character validation/promotion records + backfill

Creates ``capability_validations`` (docs/character-runtime/DESIGN.md 3.1): one
record per (character, character version, capability type, capability key,
capability version) with validation evidence, who validated and who promoted,
and retirement. Then backfills one PROMOTED record for everything customers
can use today, so nothing disappears when customer routes switch to this table
later (DESIGN.md section 8, PR 1):

* appearance options in PRODUCTION (HAIR_STYLE, MAKEUP_STYLE, EXPRESSION,
  JEWELRY, BEAUTY_DIRECTION; NAILS has no capability type yet), per their own
  character version;
* customer product types whose capability pack is in PRODUCTION;
* for each character's current locked version: the ACTIVE poses offered for a
  product type with a PRODUCTION pack (limited to the pack's
  ``compatible_poses`` when it has any), and every PRODUCTION location,
  lighting and campaign preset.

Additive and safe to run twice: the table and each index are created only when
missing (``create_table_if_absent``), and the backfill inserts only records
that do not exist yet; it never updates or deletes a row and only reads the
definition tables. The backfill rules are a frozen copy of
``app.services.capability_validations.backfill_plan`` at this revision.

Revision ID: capability_validations_001
Revises: schema_drift_001
Create Date: 2026-10-20
"""
import json
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.migration_guard import create_table_if_absent

revision = 'capability_validations_001'
down_revision = 'schema_drift_001'
branch_labels = None
depends_on = None

TABLE = 'capability_validations'
ACTOR = 'SYSTEM_BACKFILL'
APPEARANCE_TYPES = {
    'HAIR_STYLE': ('HAIR', 'hair_'),
    'MAKEUP_STYLE': ('MAKEUP', 'makeup_'),
    'EXPRESSION': ('EXPRESSION', 'expr_'),
    'JEWELRY': ('JEWELRY', 'jewelry_'),
    'BEAUTY_DIRECTION': ('BEAUTY_DIRECTION', 'beauty_'),
}
PRESET_TYPES = {
    'LOCATION': ('SCENE', 'scene_'),
    'LIGHTING': ('LIGHTING', 'lighting_'),
    'CAMPAIGN': ('CAMPAIGN', 'campaign_'),
}
PROMOTED_ONLY = "status = 'PROMOTED'"


def _jsonb():
    return sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def _ensure_table(bind):
    create_table_if_absent(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('capability_type', sa.String(30), nullable=False),
        sa.Column('capability_key', sa.String(80), nullable=False),
        sa.Column('capability_version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('customer_id', sa.String(80), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='REGISTERED'),
        sa.Column('validation', _jsonb(), nullable=True),
        sa.Column('validated_by', sa.String(100), nullable=True),
        sa.Column('validated_at', sa.DateTime, nullable=True),
        sa.Column('promoted_by', sa.String(100), nullable=True),
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        sa.Column('retired_by', sa.String(100), nullable=True),
        sa.Column('retired_at', sa.DateTime, nullable=True),
        sa.Column('retire_reason', sa.Text, nullable=True),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('recommended', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('group', sa.String(30), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('character_id', 'character_version', 'capability_type', 'capability_key',
                            'capability_version', name='uq_capability_validation_version'),
    )
    existing = {ix['name'] for ix in sa.inspect(bind).get_indexes(TABLE)}
    if 'ix_capability_validations_character_id' not in existing:
        op.create_index('ix_capability_validations_character_id', TABLE, ['character_id'])
    if 'ix_capability_validations_lookup' not in existing:
        op.create_index('ix_capability_validations_lookup', TABLE,
                        ['character_id', 'character_version', 'capability_type', 'status'])
    if 'uq_capability_validation_promoted' not in existing:
        op.create_index('uq_capability_validation_promoted', TABLE,
                        ['character_id', 'character_version', 'capability_type', 'capability_key'], unique=True,
                        postgresql_where=sa.text(PROMOTED_ONLY), sqlite_where=sa.text(PROMOTED_ONLY))
    if 'uq_capability_validation_customer_id' not in existing:
        op.create_index('uq_capability_validation_customer_id', TABLE,
                        ['character_id', 'character_version', 'customer_id'], unique=True,
                        postgresql_where=sa.text(PROMOTED_ONLY), sqlite_where=sa.text(PROMOTED_ONLY))


def _version_key(version):
    return tuple(int(part) if part.isdigit() else 0 for part in (version or '').split('.'))


def _item(character_id, character_version, capability_type, key, version, customer_id, is_default, sort_order,
          source, source_key):
    return {
        'character_id': character_id, 'character_version': character_version, 'capability_type': capability_type,
        'capability_key': key, 'capability_version': version, 'customer_id': customer_id,
        'is_default': bool(is_default), 'sort_order': sort_order or 0,
        'validation': {'backfill': {'source': source, 'source_key': source_key, 'source_status': 'PRODUCTION'}},
    }


def _rows(bind, sql, **params):
    return bind.execute(sa.text(sql), params).mappings().all()


def _current_versions(bind):
    by_character = {}
    for row in _rows(bind, 'SELECT character_id, version, status, locked FROM character_registry_versions'):
        if row['locked'] or row['status'] == 'LOCKED':
            best = by_character.get(row['character_id'])
            if best is None or _version_key(row['version']) > _version_key(best):
                by_character[row['character_id']] = row['version']
    return sorted(by_character.items())


def _offered_poses(bind, character_id, character_version, product_type, pack_type):
    pack = _rows(bind, "SELECT compatible_poses FROM capability_packs WHERE character_id = :c "
                       "AND character_version = :v AND pack_type = :p AND status = 'PRODUCTION'",
                 c=character_id, v=character_version, p=pack_type)
    if not pack:
        return []
    allowed = pack[0]['compatible_poses'] or []
    if isinstance(allowed, str):  # SQLite returns JSON as text
        allowed = json.loads(allowed)
    rows = _rows(bind, "SELECT d.pose_id, d.sort_order FROM pose_definitions d "
                       "JOIN pose_product_types m ON m.pose_definition_id = d.id "
                       "WHERE m.product_type = :t AND d.status = 'ACTIVE' "
                       "ORDER BY m.sort_order, d.sort_order, d.pose_id", t=product_type)
    return [r for r in rows if not allowed or r['pose_id'] in set(allowed)]


def backfill_plan(bind):
    """Frozen copy of app.services.capability_validations.backfill_plan."""
    plan = []
    for o in _rows(bind, "SELECT character_id, character_version, category, option_id, version, is_default, "
                         "sort_order, internal_key FROM appearance_options WHERE status = 'PRODUCTION' ORDER BY id"):
        if o['category'] not in APPEARANCE_TYPES:
            continue
        capability_type, prefix = APPEARANCE_TYPES[o['category']]
        plan.append(_item(o['character_id'], o['character_version'], capability_type, o['option_id'], o['version'],
                          prefix + o['option_id'].lower(), o['is_default'], o['sort_order'],
                          'appearance_options', o['internal_key']))

    product_types = _rows(bind, 'SELECT product_type, pack_type, is_default, sort_order '
                                'FROM capability_product_types ORDER BY id')
    for pack in _rows(bind, "SELECT character_id, character_version, pack_type, version, internal_key "
                            "FROM capability_packs WHERE status = 'PRODUCTION' ORDER BY id"):
        for pt in product_types:
            if pt['pack_type'] == pack['pack_type']:
                plan.append(_item(pack['character_id'], pack['character_version'], 'PRODUCT_TYPE', pt['product_type'],
                                  pack['version'], pt['product_type'], pt['is_default'], pt['sort_order'],
                                  'capability_packs', pack['internal_key']))

    presets = _rows(bind, "SELECT preset_type, preset_key, is_default, sort_order FROM presets "
                          "WHERE status = 'PRODUCTION' ORDER BY id")
    for character_id, character_version in _current_versions(bind):
        seen = set()
        for pt in product_types:
            for pose in _offered_poses(bind, character_id, character_version, pt['product_type'], pt['pack_type']):
                if pose['pose_id'] in seen:
                    continue
                seen.add(pose['pose_id'])
                plan.append(_item(character_id, character_version, 'POSE', pose['pose_id'], 1,
                                  'pose_' + pose['pose_id'], False, pose['sort_order'],
                                  'pose_definitions', pose['pose_id']))
        for p in presets:
            if p['preset_type'] not in PRESET_TYPES:
                continue
            capability_type, prefix = PRESET_TYPES[p['preset_type']]
            plan.append(_item(character_id, character_version, capability_type, p['preset_key'], 1,
                              prefix + p['preset_key'].lower(), p['is_default'], p['sort_order'],
                              'presets', f"{p['preset_type']}:{p['preset_key']}"))
    return plan


def backfill(bind):
    """Insert the missing plan items as PROMOTED; never touches an existing row."""
    existing = _rows(bind, f'SELECT character_id, character_version, capability_type, capability_key, '
                           f'capability_version, customer_id, status FROM {TABLE}')
    versions = {(r['character_id'], r['character_version'], r['capability_type'], r['capability_key'],
                 r['capability_version']) for r in existing}
    live = {(r['character_id'], r['character_version'], r['capability_type'], r['capability_key'])
            for r in existing if r['status'] == 'PROMOTED'}
    live_ids = {(r['character_id'], r['character_version'], r['customer_id'])
                for r in existing if r['status'] == 'PROMOTED'}
    table = sa.table(TABLE, *[sa.column(c) for c in (
        'character_id', 'character_version', 'capability_type', 'capability_key', 'capability_version',
        'customer_id', 'status', 'is_default', 'recommended', 'sort_order', 'validated_by', 'validated_at',
        'promoted_by', 'promoted_at')], sa.column('validation', _jsonb()))
    now = datetime.utcnow()
    inserted = 0
    for item in backfill_plan(bind):
        version_key = (item['character_id'], item['character_version'], item['capability_type'],
                       item['capability_key'], item['capability_version'])
        customer = (item['character_id'], item['character_version'], item['customer_id'])
        if version_key in versions or version_key[:4] in live or customer in live_ids:
            continue
        versions.add(version_key)
        live.add(version_key[:4])
        live_ids.add(customer)
        bind.execute(table.insert().values(
            **item, status='PROMOTED', recommended=False, validated_by=ACTOR, validated_at=now,
            promoted_by=ACTOR, promoted_at=now))
        inserted += 1
    return inserted


def upgrade():
    bind = op.get_bind()
    _ensure_table(bind)
    print(f'[migration] {TABLE}: backfilled {backfill(bind)} PROMOTED records')


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
