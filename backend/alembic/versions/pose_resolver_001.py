"""pose resolver - product-aware pose catalog; framing rules moved into data

Creates ``pose_definitions`` (pose catalog with admin-only technical refs) and
``pose_product_types`` (product type -> poses, at most one default per
product type via a partial unique index). Adds ``compatible_poses`` to
``capability_packs`` and ``required_framings`` / ``framing_rule_code`` to
``capability_product_types``, filled with the framing rules that used to be
hard-coded in services/compatibility.py. Seeds the pose catalog and mapping
(metadata only). Nothing here touches character_registry_versions.
Safe to run twice.

Revision ID: pose_resolver_001
Revises: capability_packs_001
Create Date: 2026-10-05
"""
import json

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'pose_resolver_001'
down_revision = 'capability_packs_001'
branch_labels = None
depends_on = None

POSES = 'pose_definitions'
MAPPINGS = 'pose_product_types'
PACKS = 'capability_packs'
PRODUCT_TYPES = 'capability_product_types'

FRAMING_RULES = (
    ('FOOTWEAR', ['FULL_BODY', 'DETAIL'], 'FOOTWEAR_REQUIRES_VISIBLE_FEET'),
    ('EYEWEAR', ['CLOSE_UP', 'BUST', 'UPPER_BODY', 'PORTRAIT'], 'EYEWEAR_REQUIRES_FACE_VISIBILITY'),
    ('JEWELRY', ['CLOSE_UP', 'BUST', 'DETAIL', 'UPPER_BODY'], 'JEWELRY_REQUIRES_CLOSE_FRAMING'),
)

# Snapshot of app.services.pose_resolver.DEFAULT_POSES at this revision.
SEED_POSES = (
    ('standing', 'Standing', 'static', 'full_body', 'Relaxed full-length standing pose that shows the whole garment.'),
    ('walking', 'Walking', 'motion', 'full_body', 'Mid-stride walk that shows how the product moves.'),
    ('editorial', 'Editorial', 'static', 'full_body', 'Styled fashion-editorial stance with more attitude than a catalog pose.'),
    ('seated', 'Seated', 'static', 'full_body', 'Seated pose that shows drape and fit when sitting.'),
    ('garment_interaction', 'Garment Interaction', 'static', 'three_quarter',
     'Hands on the garment (collar, hem, pocket) to draw attention to a detail.'),
    ('foot_forward', 'Foot Forward', 'static', 'full_body', 'Full-length stance with one foot forward to show the shoe.'),
    ('full_body_profile', 'Profile', 'static', 'full_body', "Full-length side view that shows the shoe's silhouette."),
    ('shoe_detail', 'Shoe Detail', 'detail', 'detail', 'Close crop on the feet that shows materials and finish.'),
    ('hand_carry', 'Hand Carry', 'static', 'three_quarter', 'Bag held by the handle at the side.'),
    ('shoulder_carry', 'Shoulder', 'static', 'three_quarter', 'Bag worn on the shoulder.'),
    ('crossbody', 'Crossbody', 'static', 'three_quarter', 'Bag worn across the body.'),
    ('bag_detail', 'Product Detail', 'detail', 'detail', 'Close crop on the bag that shows hardware and materials.'),
    ('portrait', 'Portrait', 'portrait', 'close_up', 'Front-facing head-and-shoulders portrait.'),
    ('head_turn_30', '30° Turn', 'portrait', 'close_up', 'Head turned 30° from camera.'),
    ('head_turn_45', '45° Turn', 'portrait', 'close_up', 'Head turned 45° from camera.'),
    ('head_profile', 'Head Profile', 'portrait', 'close_up', 'Head in side profile.'),
    ('temple_adjustment', 'Temple Adjustment', 'detail', 'close_up', 'Hand adjusting the frame at the temple.'),
    ('ear_detail', 'Ear Detail', 'detail', 'detail', 'Close crop on the ear for earrings.'),
    ('neck_detail', 'Neck Detail', 'detail', 'detail', 'Close crop on the neck and collarbone for necklaces.'),
    ('wrist_detail', 'Wrist Detail', 'detail', 'detail', 'Close crop on the wrist for bracelets and watches.'),
    ('hand_detail', 'Hand Detail', 'detail', 'detail', 'Close crop on the hand for rings.'),
)

# Product type -> poses in display order; the first one is the default.
SEED_MAPPING = (
    ('garment', ('standing', 'walking', 'editorial', 'seated', 'garment_interaction')),
    ('shoes', ('foot_forward', 'full_body_profile', 'walking', 'shoe_detail')),
    ('bags', ('hand_carry', 'shoulder_carry', 'crossbody', 'walking', 'bag_detail')),
    ('eyewear', ('portrait', 'head_turn_30', 'head_turn_45', 'head_profile', 'temple_adjustment')),
    ('jewelry', ('portrait', 'ear_detail', 'neck_detail', 'wrist_detail', 'hand_detail')),
    ('headwear', ('portrait', 'head_turn_45', 'head_profile')),
)


def _create_poses():
    op.create_table(POSES,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('pose_id', sa.String(60), unique=True, nullable=False),
        sa.Column('label', sa.String(100), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('thumbnail_url', sa.String(1000), nullable=True),
        sa.Column('recommended_framing', sa.String(20), nullable=False),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='ACTIVE'),
        sa.Column('pose_adapter_id', sa.String(50), nullable=True),
        sa.Column('geometry_preset_id', sa.String(50), nullable=True),
        sa.Column('control_reference', JSONB, nullable=True),
        sa.Column('workflow_params', JSONB, nullable=True),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('updated_by', sa.String(100), nullable=True),
        sa.Column('archived_by', sa.String(100), nullable=True),
        sa.Column('archived_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )


def _create_mappings():
    op.create_table(MAPPINGS,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('pose_definition_id', sa.Integer, sa.ForeignKey(f'{POSES}.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_type', sa.String(30), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('sort_order', sa.Integer, nullable=False, server_default='0'),
        sa.UniqueConstraint('pose_definition_id', 'product_type', name='uq_pose_product_type'),
    )
    op.create_index('ix_pose_product_types_pose_definition_id', MAPPINGS, ['pose_definition_id'])
    op.create_index('ix_pose_product_types_product_type', MAPPINGS, ['product_type'])
    op.create_index('uq_pose_product_type_default', MAPPINGS, ['product_type'],
                    unique=True, postgresql_where=sa.text('is_default'))


def _add_columns(inspector):
    pack_columns = {c['name'] for c in inspector.get_columns(PACKS)}
    if 'compatible_poses' not in pack_columns:
        op.add_column(PACKS, sa.Column('compatible_poses', JSONB, nullable=True))
    type_columns = {c['name'] for c in inspector.get_columns(PRODUCT_TYPES)}
    if 'required_framings' not in type_columns:
        op.add_column(PRODUCT_TYPES, sa.Column('required_framings', JSONB, nullable=True))
    if 'framing_rule_code' not in type_columns:
        op.add_column(PRODUCT_TYPES, sa.Column('framing_rule_code', sa.String(60), nullable=True))


def _seed_framing_rules(bind):
    for pack_type, framings, code in FRAMING_RULES:
        bind.execute(sa.text(
            f"UPDATE {PRODUCT_TYPES} SET required_framings = CAST(:f AS JSONB), framing_rule_code = :c "
            "WHERE pack_type = :p AND required_framings IS NULL"
        ), {'f': json.dumps(framings), 'c': code, 'p': pack_type})


def _seed_poses(bind):
    poses = sa.table(POSES, *[sa.column(c) for c in (
        'pose_id', 'label', 'category', 'recommended_framing', 'description', 'sort_order', 'status', 'created_by')])
    for order, (pose_id, label, category, framing, description) in enumerate(SEED_POSES, start=1):
        if bind.execute(sa.text(f"SELECT 1 FROM {POSES} WHERE pose_id = :p"), {'p': pose_id}).first():
            continue
        bind.execute(poses.insert().values(
            pose_id=pose_id, label=label, category=category, recommended_framing=framing, description=description,
            sort_order=order * 10, status='ACTIVE', created_by='SYSTEM_SEED'))

    mappings = sa.table(MAPPINGS, *[sa.column(c) for c in (
        'pose_definition_id', 'product_type', 'is_default', 'sort_order')])
    ids = {row.pose_id: row.id for row in bind.execute(sa.text(f"SELECT id, pose_id FROM {POSES}"))}
    for product_type, pose_ids in SEED_MAPPING:
        has_default = bind.execute(sa.text(
            f"SELECT 1 FROM {MAPPINGS} WHERE product_type = :t AND is_default"), {'t': product_type}).first()
        for order, pose_id in enumerate(pose_ids, start=1):
            if bind.execute(sa.text(
                    f"SELECT 1 FROM {MAPPINGS} WHERE pose_definition_id = :i AND product_type = :t"),
                    {'i': ids[pose_id], 't': product_type}).first():
                continue
            bind.execute(mappings.insert().values(
                pose_definition_id=ids[pose_id], product_type=product_type, sort_order=order * 10,
                is_default=order == 1 and not has_default))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    _add_columns(inspector)
    if not inspector.has_table(POSES):
        _create_poses()
    if not inspector.has_table(MAPPINGS):
        _create_mappings()
    _seed_framing_rules(bind)
    _seed_poses(bind)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for table in (MAPPINGS, POSES):
        if inspector.has_table(table):
            op.drop_table(table)
    for table, column in ((PACKS, 'compatible_poses'), (PRODUCT_TYPES, 'framing_rule_code'),
                          (PRODUCT_TYPES, 'required_framings')):
        if column in {c['name'] for c in inspector.get_columns(table)}:
            op.drop_column(table, column)
