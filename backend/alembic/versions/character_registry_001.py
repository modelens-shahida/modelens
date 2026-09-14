"""character registry - CharacterIdentityProfile, CharacterBodyProfile, CharacterSkinProfile, CharacterHairProfile, CharacterRuntimeProfile

Revision ID: character_registry_001
Revises: workspace_isolation_001
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'character_registry_001'
down_revision = 'workspace_isolation_001'
branch_labels = None
depends_on = None


def upgrade():
    # Character Identity Profile
    op.create_table('character_identity_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False, unique=True),
        sa.Column('workspace_id', sa.String(50), nullable=True),
        sa.Column('internal_name', sa.String(100), nullable=True),
        sa.Column('display_name', sa.String(100), nullable=True),
        sa.Column('status', sa.String(50), default='CHAR_CONCEPT'),
        sa.Column('age_anchor', sa.Integer, nullable=True),
        sa.Column('face_shape', sa.String(20), nullable=True),
        sa.Column('eye_shape', sa.String(20), nullable=True),
        sa.Column('eye_spacing', sa.String(20), nullable=True),
        sa.Column('nose_bridge', sa.String(20), nullable=True),
        sa.Column('nose_width', sa.String(20), nullable=True),
        sa.Column('cheekbone_height', sa.String(20), nullable=True),
        sa.Column('jaw_width', sa.String(20), nullable=True),
        sa.Column('chin_shape', sa.String(20), nullable=True),
        sa.Column('identity_markers', JSONB, nullable=True),
        sa.Column('locked_fields', JSONB, nullable=True),
        sa.Column('customer_visible', sa.Boolean, default=False),
        sa.Column('production_enabled', sa.Boolean, default=False),
        sa.Column('golden_character_version', sa.String(10), nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_identity_character_id', 'character_identity_profiles', ['character_id'])

    # Character Body Profile
    op.create_table('character_body_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('body_profile_id', sa.String(50), nullable=False, unique=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('height_cm', sa.Float, nullable=True),
        sa.Column('height_band', sa.String(10), nullable=True),
        sa.Column('build_code', sa.String(10), nullable=True),
        sa.Column('frame_code', sa.String(10), nullable=True),
        sa.Column('head_body_ratio', sa.Float, nullable=True),
        sa.Column('shoulders_width', sa.String(10), nullable=True),
        sa.Column('shoulders_slope', sa.String(10), nullable=True),
        sa.Column('torso_length', sa.String(10), nullable=True),
        sa.Column('waist_position', sa.String(10), nullable=True),
        sa.Column('hip_width', sa.String(10), nullable=True),
        sa.Column('leg_proportion', sa.String(10), nullable=True),
        sa.Column('arm_length', sa.String(10), nullable=True),
        sa.Column('status', sa.String(30), default='DRAFT'),
        sa.Column('version', sa.String(10), default='1.0'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_body_character_id', 'character_body_profiles', ['character_id'])

    # Character Skin Profile
    op.create_table('character_skin_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('skin_profile_id', sa.String(50), nullable=False, unique=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('depth_code', sa.String(10), nullable=True),
        sa.Column('undertone_code', sa.String(10), nullable=True),
        sa.Column('chroma_code', sa.String(10), nullable=True),
        sa.Column('translucency_code', sa.String(10), nullable=True),
        sa.Column('pore_density', sa.String(10), nullable=True),
        sa.Column('pore_visibility', sa.String(10), nullable=True),
        sa.Column('microtexture', sa.String(10), nullable=True),
        sa.Column('vellus_hair', sa.String(10), nullable=True),
        sa.Column('under_eye_texture', sa.String(10), nullable=True),
        sa.Column('sebum_code', sa.String(10), nullable=True),
        sa.Column('age_profile', sa.String(10), nullable=True),
        sa.Column('permanent_markers', JSONB, nullable=True),
        sa.Column('status', sa.String(30), default='DRAFT'),
        sa.Column('version', sa.String(10), default='1.0'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_skin_character_id', 'character_skin_profiles', ['character_id'])

    # Character Hair Profile
    op.create_table('character_hair_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('hair_dna_id', sa.String(50), nullable=False, unique=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('natural_color', sa.String(15), nullable=True),
        sa.Column('undertone', sa.String(15), nullable=True),
        sa.Column('hairline', sa.String(15), nullable=True),
        sa.Column('density', sa.String(15), nullable=True),
        sa.Column('strand_thickness', sa.String(15), nullable=True),
        sa.Column('natural_texture', sa.String(15), nullable=True),
        sa.Column('canonical_length', sa.String(15), nullable=True),
        sa.Column('canonical_part', sa.String(15), nullable=True),
        sa.Column('status', sa.String(30), default='DRAFT'),
        sa.Column('version', sa.String(10), default='1.0'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_hair_character_id', 'character_hair_profiles', ['character_id'])

    # Character Runtime Profile
    op.create_table('character_runtime_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('runtime_profile_id', sa.String(50), nullable=False, unique=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('character_version', sa.String(10), nullable=True),
        sa.Column('identity_profile_id', sa.String(50), nullable=True),
        sa.Column('body_profile_id', sa.String(50), nullable=True),
        sa.Column('skin_profile_id', sa.String(50), nullable=True),
        sa.Column('hair_profile_id', sa.String(50), nullable=True),
        sa.Column('production_model_alias', sa.String(100), nullable=True),
        sa.Column('default_strength', sa.Float, default=0.78),
        sa.Column('approved_workflows', JSONB, nullable=True),
        sa.Column('strength_overrides', JSONB, nullable=True),
        sa.Column('status', sa.String(30), default='DRAFT'),
        sa.Column('production_enabled', sa.Boolean, default=False),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_runtime_character_id', 'character_runtime_profiles', ['character_id'])


def downgrade():
    op.drop_table('character_runtime_profiles')
    op.drop_table('character_hair_profiles')
    op.drop_table('character_skin_profiles')
    op.drop_table('character_body_profiles')
    op.drop_table('character_identity_profiles')
