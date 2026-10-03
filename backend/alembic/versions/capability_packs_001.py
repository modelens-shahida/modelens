"""capability packs - capabilities layered on a Character Version; seed the product type mapping

Creates ``capability_packs`` (at most one PRODUCTION version per character and
pack type, via a partial unique index), ``capability_pack_adapters`` (links to
Training Registry adapters) and ``capability_product_types`` (customer
product type -> pack type), and seeds that mapping. No pack is seeded: none
has been validated yet. Nothing here touches character_registry_versions.
Safe to run twice.

Revision ID: capability_packs_001
Revises: appearance_options_001
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'capability_packs_001'
down_revision = 'appearance_options_001'
branch_labels = None
depends_on = None

PACKS = 'capability_packs'
LINKS = 'capability_pack_adapters'
PRODUCT_TYPES = 'capability_product_types'

SEED = (
    ('garment', 'GARMENT', 'Garment', 10),
    ('shoes', 'FOOTWEAR', 'Footwear', 20),
    ('bags', 'BAGS', 'Bags', 30),
    ('eyewear', 'EYEWEAR', 'Eyewear', 40),
    ('headwear', 'HEADWEAR', 'Headwear', 50),
    ('jewelry', 'JEWELRY', 'Jewelry', 60),
)


def _create_packs():
    op.create_table(PACKS,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('internal_key', sa.String(120), unique=True, nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=False),
        sa.Column('pack_type', sa.String(30), nullable=False),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='IN_DEVELOPMENT'),
        sa.Column('workflow_route', sa.String(100), nullable=True),
        sa.Column('workflow_version', sa.String(20), nullable=True),
        sa.Column('required_reference_assets', JSONB, nullable=True),
        sa.Column('validation', JSONB, nullable=True),
        sa.Column('supported_product_types', JSONB, nullable=True),
        sa.Column('compatible_appearance_options', JSONB, nullable=True),
        sa.Column('qa_rules', JSONB, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('status_changed_by', sa.String(100), nullable=True),
        sa.Column('status_changed_at', sa.DateTime, nullable=True),
        sa.Column('validated_by', sa.String(100), nullable=True),
        sa.Column('validated_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('character_id', 'pack_type', 'version', name='uq_capability_pack_version'),
    )
    op.create_index('ix_capability_packs_character_id', PACKS, ['character_id'])
    op.create_index('uq_capability_pack_production', PACKS, ['character_id', 'pack_type'],
                    unique=True, postgresql_where=sa.text("status = 'PRODUCTION'"))


def _create_links():
    op.create_table(LINKS,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('pack_id', sa.Integer, sa.ForeignKey(f'{PACKS}.id', ondelete='CASCADE'), nullable=False),
        sa.Column('adapter_id', sa.String(50), nullable=False),
        sa.Column('linked_by', sa.String(100), nullable=True),
        sa.Column('linked_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('pack_id', 'adapter_id', name='uq_capability_pack_adapter'),
    )
    op.create_index('ix_capability_pack_adapters_pack_id', LINKS, ['pack_id'])


def _create_product_types():
    op.create_table(PRODUCT_TYPES,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('product_type', sa.String(30), unique=True, nullable=False),
        sa.Column('pack_type', sa.String(30), nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
    )


def _seed(bind):
    rows = sa.table(PRODUCT_TYPES, *[sa.column(c) for c in (
        'product_type', 'pack_type', 'label', 'is_default', 'sort_order')])
    for product_type, pack_type, label, sort_order in SEED:
        if bind.execute(sa.text(f"SELECT 1 FROM {PRODUCT_TYPES} WHERE product_type = :p"),
                        {'p': product_type}).first():
            continue
        bind.execute(rows.insert().values(product_type=product_type, pack_type=pack_type, label=label,
                                          is_default=False, sort_order=sort_order))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(PACKS):
        _create_packs()
    if not inspector.has_table(LINKS):
        _create_links()
    if not inspector.has_table(PRODUCT_TYPES):
        _create_product_types()
    _seed(bind)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in (LINKS, PACKS, PRODUCT_TYPES):
        if inspector.has_table(table):
            op.drop_table(table)
