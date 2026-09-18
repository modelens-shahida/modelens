"""character registry v2 - Full Character DNA, Versioning, Canonical Assets, QA, Lineage

Revision ID: character_registry_v2_001
Revises: dataset_registry_001
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'character_registry_v2_001'
down_revision = 'dataset_registry_001'
branch_labels = None
depends_on = None


def upgrade():
    # ==================== Character Master ====================
    op.create_table('characters_v2',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('internal_name', sa.String(100), nullable=True),
        sa.Column('workspace_id', sa.String(50), nullable=True),
        sa.Column('gender_presentation', sa.String(20), nullable=True),
        sa.Column('status', sa.String(30), default='DEVELOPMENT'),
        sa.Column('current_version', sa.String(10), default='0.1'),
        sa.Column('customer_visible', sa.Boolean, default=False),
        sa.Column('production_enabled', sa.Boolean, default=False),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_characters_v2_character_id', 'characters_v2', ['character_id'])
    op.create_index('ix_characters_v2_status', 'characters_v2', ['status'])

    # ==================== Character Version ====================
    op.create_table('character_versions',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),
        sa.Column('status', sa.String(30), default='DEVELOPMENT'),
        sa.Column('locked', sa.Boolean, default=False),
        sa.Column('locked_at', sa.DateTime, nullable=True),
        sa.Column('locked_by', sa.String(100), nullable=True),
        sa.Column('promoted_to_production', sa.Boolean, default=False),
        sa.Column('promoted_at', sa.DateTime, nullable=True),
        sa.Column('taxonomy_version', sa.String(20), nullable=True),
        sa.Column('dna_snapshot', JSONB, nullable=True),
        sa.Column('qa_snapshot', JSONB, nullable=True),
        sa.Column('release_notes', sa.Text, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_versions_character_id', 'character_versions', ['character_id'])
    op.create_unique_constraint('uq_char_version', 'character_versions', ['character_id', 'version'])

    # ==================== Identity DNA ====================
    op.create_table('character_identity_dna',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),

        # Face geometry
        sa.Column('face_shape', sa.String(20), nullable=True),
        sa.Column('face_width', sa.String(20), nullable=True),
        sa.Column('face_length', sa.String(20), nullable=True),
        sa.Column('face_symmetry', sa.String(20), nullable=True),

        # Eye characteristics
        sa.Column('eye_shape', sa.String(20), nullable=True),
        sa.Column('eye_size', sa.String(20), nullable=True),
        sa.Column('eye_spacing', sa.String(20), nullable=True),
        sa.Column('eye_color', sa.String(20), nullable=True),
        sa.Column('eye_depth', sa.String(20), nullable=True),
        sa.Column('eye_angle', sa.String(20), nullable=True),

        # Brow characteristics
        sa.Column('brow_shape', sa.String(20), nullable=True),
        sa.Column('brow_thickness', sa.String(20), nullable=True),
        sa.Column('brow_position', sa.String(20), nullable=True),
        sa.Column('brow_arch', sa.String(20), nullable=True),

        # Nose characteristics
        sa.Column('nose_bridge', sa.String(20), nullable=True),
        sa.Column('nose_width', sa.String(20), nullable=True),
        sa.Column('nose_length', sa.String(20), nullable=True),
        sa.Column('nose_tip', sa.String(20), nullable=True),
        sa.Column('nose_profile', sa.String(20), nullable=True),

        # Mouth/lip characteristics
        sa.Column('lip_shape', sa.String(20), nullable=True),
        sa.Column('lip_fullness', sa.String(20), nullable=True),
        sa.Column('lip_width', sa.String(20), nullable=True),
        sa.Column('mouth_position', sa.String(20), nullable=True),
        sa.Column('philtrum', sa.String(20), nullable=True),

        # Cheek structure
        sa.Column('cheekbone_height', sa.String(20), nullable=True),
        sa.Column('cheekbone_prominence', sa.String(20), nullable=True),
        sa.Column('cheek_fullness', sa.String(20), nullable=True),

        # Jaw/chin structure
        sa.Column('jaw_width', sa.String(20), nullable=True),
        sa.Column('jaw_angle', sa.String(20), nullable=True),
        sa.Column('chin_shape', sa.String(20), nullable=True),
        sa.Column('chin_projection', sa.String(20), nullable=True),

        # Hairline and ears
        sa.Column('hairline_shape', sa.String(20), nullable=True),
        sa.Column('hairline_height', sa.String(20), nullable=True),
        sa.Column('ear_size', sa.String(20), nullable=True),
        sa.Column('ear_position', sa.String(20), nullable=True),

        # Identity anchors
        sa.Column('age_anchor', sa.Integer, nullable=True),
        sa.Column('gender_presentation', sa.String(20), nullable=True),
        sa.Column('identity_markers', JSONB, nullable=True),
        sa.Column('landmark_profile', JSONB, nullable=True),

        sa.Column('status', sa.String(20), default='DRAFT'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_identity_dna_character', 'character_identity_dna', ['character_id', 'version'])

    # ==================== Body DNA ====================
    op.create_table('character_body_dna',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),

        # Height and stature
        sa.Column('canonical_height_cm', sa.Float, nullable=True),
        sa.Column('height_status', sa.String(20), default='ESTIMATED'),
        sa.Column('stature_class', sa.String(30), nullable=True),
        sa.Column('body_scale_class', sa.String(20), nullable=True),
        sa.Column('body_archetype', sa.String(50), nullable=True),
        sa.Column('visual_stature_target', sa.String(30), nullable=True),
        sa.Column('proportion_profile_id', sa.String(50), nullable=True),

        # Head and torso
        sa.Column('head_to_body_ratio', sa.String(20), nullable=True),
        sa.Column('shoulder_width_class', sa.String(20), nullable=True),
        sa.Column('ribcage_profile', sa.String(20), nullable=True),
        sa.Column('bust_profile', sa.String(20), nullable=True),
        sa.Column('waist_profile', sa.String(20), nullable=True),
        sa.Column('pelvis_profile', sa.String(20), nullable=True),
        sa.Column('hip_profile', sa.String(20), nullable=True),

        # Torso proportions
        sa.Column('torso_length', sa.String(20), nullable=True),
        sa.Column('waist_height', sa.String(20), nullable=True),
        sa.Column('pelvis_height', sa.String(20), nullable=True),

        # Leg proportions
        sa.Column('femur_ratio', sa.String(20), nullable=True),
        sa.Column('knee_height', sa.String(20), nullable=True),
        sa.Column('tibia_ratio', sa.String(20), nullable=True),
        sa.Column('thigh_profile', sa.String(20), nullable=True),
        sa.Column('calf_profile', sa.String(20), nullable=True),
        sa.Column('ankle_profile', sa.String(20), nullable=True),
        sa.Column('foot_scale', sa.String(20), nullable=True),

        # Arm proportions
        sa.Column('upper_arm_ratio', sa.String(20), nullable=True),
        sa.Column('forearm_ratio', sa.String(20), nullable=True),
        sa.Column('hand_scale', sa.String(20), nullable=True),

        sa.Column('status', sa.String(20), default='DRAFT'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_body_dna_character', 'character_body_dna', ['character_id', 'version'])

    # ==================== Appearance Profile ====================
    op.create_table('character_appearance_profiles',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),

        # Base skin
        sa.Column('skin_depth_code', sa.String(15), nullable=True),
        sa.Column('skin_undertone', sa.String(15), nullable=True),
        sa.Column('skin_chroma', sa.String(15), nullable=True),
        sa.Column('skin_texture', sa.String(15), nullable=True),
        sa.Column('skin_pore_density', sa.String(15), nullable=True),

        # Base hair
        sa.Column('hair_color', sa.String(20), nullable=True),
        sa.Column('hair_undertone', sa.String(20), nullable=True),
        sa.Column('hair_texture', sa.String(20), nullable=True),
        sa.Column('hair_density', sa.String(20), nullable=True),
        sa.Column('hair_canonical_length', sa.String(20), nullable=True),
        sa.Column('hair_canonical_style', sa.String(30), nullable=True),

        # Base makeup
        sa.Column('makeup_base', sa.String(20), default='MINIMAL'),
        sa.Column('makeup_profile', JSONB, nullable=True),

        sa.Column('status', sa.String(20), default='DRAFT'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_appearance_character', 'character_appearance_profiles', ['character_id', 'version'])

    # ==================== Canonical Asset Registry ====================
    op.create_table('canonical_assets',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('asset_id', sa.String(50), unique=True, nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),

        # Asset role
        sa.Column('asset_role', sa.String(50), nullable=False),
        sa.Column('framing', sa.String(30), nullable=True),
        sa.Column('angle_code', sa.String(10), nullable=True),

        # Structured geometry
        sa.Column('camera_yaw_deg', sa.Float, default=0.0),
        sa.Column('camera_pitch_deg', sa.Float, default=0.0),
        sa.Column('camera_roll_deg', sa.Float, default=0.0),
        sa.Column('body_yaw_deg', sa.Float, default=0.0),
        sa.Column('head_relative_to_body_deg', sa.Float, default=0.0),
        sa.Column('head_pitch_deg', sa.Float, default=0.0),
        sa.Column('head_roll_deg', sa.Float, default=0.0),
        sa.Column('gaze', sa.String(20), default='FOLLOW_HEAD'),
        sa.Column('expression', sa.String(20), default='NEUTRAL'),
        sa.Column('pose_id', sa.String(30), nullable=True),

        # File info
        sa.Column('filename', sa.String(500), nullable=True),
        sa.Column('original_filename', sa.String(500), nullable=True),
        sa.Column('storage_path', sa.String(1000), nullable=True),
        sa.Column('content_hash_sha256', sa.String(64), nullable=True),
        sa.Column('width_px', sa.Integer, nullable=True),
        sa.Column('height_px', sa.Integer, nullable=True),
        sa.Column('mime_type', sa.String(50), nullable=True),

        # QA
        sa.Column('identity_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('body_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('hands_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('feet_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('angle_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('artifact_qa', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('overall_qa_status', sa.String(20), default='NOT_REVIEWED'),

        # Eligibility
        sa.Column('training_eligible', sa.Boolean, default=False),
        sa.Column('validation_eligible', sa.Boolean, default=False),
        sa.Column('production_reference_eligible', sa.Boolean, default=False),

        # Asset lineage
        sa.Column('parent_asset_ids', JSONB, nullable=True),
        sa.Column('source_asset_ids', JSONB, nullable=True),
        sa.Column('workflow_id', sa.String(50), nullable=True),
        sa.Column('workflow_version', sa.String(20), nullable=True),
        sa.Column('prompt_version', sa.String(20), nullable=True),
        sa.Column('taxonomy_version', sa.String(20), nullable=True),
        sa.Column('seed', sa.BigInteger, nullable=True),
        sa.Column('generation_parameters', JSONB, nullable=True),
        sa.Column('model_route', sa.String(100), nullable=True),
        sa.Column('quality_mode', sa.String(30), nullable=True),

        # Preservation roles
        sa.Column('region_roles', JSONB, nullable=True),

        # Reference authority
        sa.Column('reference_authority_role', sa.String(50), nullable=True),

        sa.Column('status', sa.String(20), default='CANDIDATE'),
        sa.Column('active_canonical', sa.Boolean, default=False),
        sa.Column('created_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_canonical_assets_character', 'canonical_assets', ['character_id', 'version'])
    op.create_index('ix_canonical_assets_role', 'canonical_assets', ['asset_role'])
    op.create_index('ix_canonical_assets_active', 'canonical_assets', ['character_id', 'active_canonical'])

    # ==================== Character Version QA Gates ====================
    op.create_table('character_version_qa',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),
        sa.Column('identity_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('body_profile_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('half_body_angle_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('full_body_angle_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('hands_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('feet_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('training_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('production_gate', sa.String(20), default='NOT_REVIEWED'),
        sa.Column('reviewed_by', sa.String(100), nullable=True),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_version_qa', 'character_version_qa', ['character_id', 'version'])

    # ==================== Character Runtime Profile V2 ====================
    op.create_table('character_runtime_v2',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('runtime_id', sa.String(50), unique=True, nullable=False),
        sa.Column('character_id', sa.String(50), nullable=False),
        sa.Column('version', sa.String(10), nullable=False),
        sa.Column('identity_dna_id', sa.Integer, nullable=True),
        sa.Column('body_dna_id', sa.Integer, nullable=True),
        sa.Column('appearance_profile_id', sa.Integer, nullable=True),
        sa.Column('production_model_alias', sa.String(100), nullable=True),
        sa.Column('default_strength', sa.Float, default=0.78),
        sa.Column('strength_overrides', JSONB, nullable=True),
        sa.Column('approved_workflows', JSONB, nullable=True),
        sa.Column('golden_reference_set', JSONB, nullable=True),
        sa.Column('status', sa.String(20), default='DRAFT'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_char_runtime_v2_character', 'character_runtime_v2', ['character_id', 'version'])


def downgrade():
    op.drop_table('character_runtime_v2')
    op.drop_table('character_version_qa')
    op.drop_table('canonical_assets')
    op.drop_table('character_appearance_profiles')
    op.drop_table('character_body_dna')
    op.drop_table('character_identity_dna')
    op.drop_table('character_versions')
    op.drop_table('characters_v2')
