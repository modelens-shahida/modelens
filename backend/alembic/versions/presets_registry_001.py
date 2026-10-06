"""presets registry - location, lighting and campaign presets with a lifecycle

Creates ``presets`` (one row per LOCATION / LIGHTING / CAMPAIGN preset, unique
per type + key, at most one default per type) and seeds the values Production
Dispatch accepted before the registry existed as PRODUCTION, so existing
requests keep working. The table is created with ``create_table_if_absent``
(an existing table must match exactly), indexes only when missing, and seed
rows only when missing: safe to run twice.

Revision ID: presets_registry_001
Revises: production_dispatch_001
Create Date: 2026-10-06
"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from app.migration_guard import create_table_if_absent

revision = 'presets_registry_001'
down_revision = 'production_dispatch_001'
branch_labels = None
depends_on = None

TABLE = 'presets'

# Frozen copy of app.services.presets_registry.SEED at this revision:
# (type, key, label, description, recommended_lighting_id, technical_config, is_default)
SEED = (
    ('LIGHTING', 'STUDIO_SOFT_DIFFUSE', 'Soft Studio', '3-point softbox wrap lighting with balanced fill', None,
     {'name': 'Studio Soft Diffuse', 'family': 'studio', 'taxonomy_id': 'LGT-CAT-001',
      'workflow_params': {'key_light': 'large_softbox_left_30deg', 'fill_light': 'soft_reflector_right',
                          'rim_light': 'subtle_back_light', 'contrast': 'low', 'color_temperature': 5400,
                          'hardness': 'very_soft'},
      'recommended_for': ['catalog', 'ecommerce', 'beauty']}, True),
    ('LIGHTING', 'EDITORIAL_HARD_HIGH_KEY', 'High Key Editorial',
     'Crisp directional light creating high-contrast edge highlights', None,
     {'name': 'Editorial Hard High Key', 'family': 'editorial', 'taxonomy_id': 'LGT-ED-004',
      'workflow_params': {'key_light': 'directional_hard_45deg', 'fill_light': 'minimal', 'contrast': 'high',
                          'color_temperature': 5600, 'hardness': 'hard'},
      'recommended_for': ['editorial', 'campaign', 'luxury']}, False),
    ('LIGHTING', 'NATURAL_GOLDEN_HOUR', 'Golden Hour', 'Warm low-angle ambient sunlight with amber rim illumination',
     None,
     {'name': 'Natural Golden Hour', 'family': 'natural', 'taxonomy_id': 'LGT-GH-001',
      'workflow_params': {'key_light': 'low_angle_sun_back_left', 'fill_light': 'ambient_sky',
                          'rim_light': 'amber_warm', 'contrast': 'medium', 'color_temperature': 3800,
                          'hardness': 'soft'},
      'recommended_for': ['editorial', 'campaign', 'resort', 'bridal']}, False),
    ('LIGHTING', 'DRAMATIC_CHIAROSCURO', 'Chiaroscuro', 'Deep sculptural shadows for luxury couture', None,
     {'name': 'Dramatic Chiaroscuro', 'family': 'editorial', 'taxonomy_id': 'LGT-ED-003',
      'workflow_params': {'key_light': 'single_directional_large_softbox_45deg', 'fill_light': 'none',
                          'contrast': 'very_high', 'color_temperature': 5200, 'hardness': 'medium_soft',
                          'shadow_depth': 'deep'},
      'recommended_for': ['luxury', 'couture', 'editorial', 'evening']}, False),
    ('LIGHTING', 'CYBERPUNK_NEON', 'Neon Glow', 'Multi-hue specular bounce for avant-garde campaigns', None,
     {'name': 'Cyberpunk Neon', 'family': 'experimental', 'taxonomy_id': 'LGT-EXP-001',
      'workflow_params': {'key_light': 'neon_blue_left', 'fill_light': 'neon_pink_right',
                          'rim_light': 'neon_purple_back', 'contrast': 'high', 'color_temperature': 'mixed',
                          'hardness': 'medium', 'specular_intensity': 0.8},
      'recommended_for': ['avant_garde', 'campaign', 'editorial']}, False),
    ('LOCATION', 'ENV-STU-0001', 'White Seamless', None, 'STUDIO_SOFT_DIFFUSE', {'family': 'STUDIO'}, True),
    ('LOCATION', 'ENV-STU-0002', 'Warm Gray Studio', None, 'STUDIO_SOFT_DIFFUSE', {'family': 'STUDIO'}, False),
    ('LOCATION', 'ENV-STU-0003', 'Cream Studio', None, 'STUDIO_SOFT_DIFFUSE', {'family': 'STUDIO'}, False),
    ('LOCATION', 'ENV-STU-0004', 'Black Studio', None, 'DRAMATIC_CHIAROSCURO', {'family': 'STUDIO'}, False),
    ('LOCATION', 'ENV-INT-0001', 'Minimal Interior', None, 'STUDIO_SOFT_DIFFUSE', {'family': 'INTERIOR'}, False),
    ('LOCATION', 'ENV-INT-0002', 'Luxury Hotel', None, 'DRAMATIC_CHIAROSCURO', {'family': 'INTERIOR'}, False),
    ('LOCATION', 'ENV-BCH-0001', 'Beach Golden Hour', None, 'NATURAL_GOLDEN_HOUR', {'family': 'BEACH'}, False),
    ('LOCATION', 'ENV-URB-0001', 'City Street', None, 'EDITORIAL_HARD_HIGH_KEY', {'family': 'URBAN'}, False),
    ('CAMPAIGN', 'ecommerce', 'E-commerce', None, None,
     {'lighting_id': 'STUDIO_SOFT_DIFFUSE', 'focal_length_mm': 85}, True),
    ('CAMPAIGN', 'catalog', 'Catalog', None, None, {'lighting_id': 'STUDIO_SOFT_DIFFUSE', 'focal_length_mm': 85}, False),
    ('CAMPAIGN', 'editorial', 'Editorial', None, None,
     {'lighting_id': 'EDITORIAL_HARD_HIGH_KEY', 'focal_length_mm': 50}, False),
    ('CAMPAIGN', 'lookbook', 'Lookbook', None, None, {'lighting_id': 'NATURAL_GOLDEN_HOUR', 'focal_length_mm': 50}, False),
    ('CAMPAIGN', 'social', 'Social', None, None, {'lighting_id': 'NATURAL_GOLDEN_HOUR', 'focal_length_mm': 35}, False),
)


def _ensure_table(bind):
    create_table_if_absent(TABLE,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('preset_type', sa.String(20), nullable=False),
        sa.Column('preset_key', sa.String(60), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='IN_DEVELOPMENT'),
        sa.Column('recommended_lighting_id', sa.String(60), nullable=True),
        sa.Column('technical_config', JSONB, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('status_changed_by', sa.String(100), nullable=True),
        sa.Column('status_changed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('preset_type', 'preset_key', name='uq_preset_type_key'),
    )
    existing = {ix['name'] for ix in sa.inspect(bind).get_indexes(TABLE)}
    if 'ix_presets_preset_type' not in existing:
        op.create_index('ix_presets_preset_type', TABLE, ['preset_type'])
    if 'uq_preset_default' not in existing:
        op.create_index('uq_preset_default', TABLE, ['preset_type'], unique=True,
                        postgresql_where=sa.text('is_default'))


def _seed(bind):
    presets = sa.table(TABLE, *[sa.column(c) for c in (
        'preset_type', 'preset_key', 'label', 'description', 'recommended_lighting_id', 'is_default',
        'sort_order', 'status', 'created_by', 'status_changed_by', 'status_changed_at',
    )], sa.column('technical_config', JSONB))
    order: dict[str, int] = {}
    for preset_type, key, label, description, lighting, config, is_default in SEED:
        sort_order = order[preset_type] = order.get(preset_type, -1) + 1
        if bind.execute(sa.text(f"SELECT 1 FROM {TABLE} WHERE preset_type = :t AND preset_key = :k"),
                        {'t': preset_type, 'k': key}).first():
            continue
        has_default = bind.execute(sa.text(f"SELECT 1 FROM {TABLE} WHERE preset_type = :t AND is_default"),
                                   {'t': preset_type}).first()
        bind.execute(presets.insert().values(
            preset_type=preset_type, preset_key=key, label=label, description=description,
            recommended_lighting_id=lighting, technical_config=config,
            is_default=is_default and has_default is None, sort_order=sort_order, status='PRODUCTION',
            created_by='SYSTEM_SEED', status_changed_by='SYSTEM_SEED', status_changed_at=datetime.utcnow(),
        ))


def upgrade():
    bind = op.get_bind()
    _ensure_table(bind)
    _seed(bind)


def downgrade():
    if sa.inspect(op.get_bind()).has_table(TABLE):
        op.drop_table(TABLE)
