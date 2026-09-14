"""pose geometry separation - body_yaw, head_yaw, head_pitch as independent fields

Revision ID: pose_geometry_separation_001
Revises: provider_abstraction_001
Create Date: 2026-09-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'pose_geometry_separation_001'
down_revision = 'provider_abstraction_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add geometry fields to angle_shots
    op.add_column('angle_shots', sa.Column('body_yaw', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('body_pitch', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('body_roll', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('head_yaw', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('head_pitch', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('head_roll', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('gaze', sa.String(20), nullable=True))
    op.add_column('angle_shots', sa.Column('expression_id', sa.String(30), nullable=True))

    # Add geometry fields to catalog_job_items
    op.add_column('catalog_job_items', sa.Column('body_yaw', sa.String(20), nullable=True))
    op.add_column('catalog_job_items', sa.Column('head_yaw', sa.String(20), nullable=True))
    op.add_column('catalog_job_items', sa.Column('head_pitch', sa.String(20), nullable=True))
    op.add_column('catalog_job_items', sa.Column('gaze', sa.String(20), nullable=True))
    op.add_column('catalog_job_items', sa.Column('expression_id', sa.String(30), nullable=True))

    # Create pose_geometry_presets table
    op.create_table('pose_geometry_presets',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('preset_id', sa.String(50), unique=True, nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('family', sa.String(50), nullable=True),

        # Body geometry
        sa.Column('body_yaw', sa.String(20), nullable=True),
        sa.Column('body_pitch', sa.String(20), nullable=True),
        sa.Column('body_roll', sa.String(20), nullable=True),

        # Head geometry - independent from body
        sa.Column('head_yaw', sa.String(20), nullable=True),
        sa.Column('head_pitch', sa.String(20), nullable=True),
        sa.Column('head_roll', sa.String(20), nullable=True),

        # Gaze and expression
        sa.Column('gaze', sa.String(20), nullable=True),
        sa.Column('expression_id', sa.String(30), nullable=True),

        # Stance and weight
        sa.Column('stance_id', sa.String(20), nullable=True),
        sa.Column('weight_distribution', sa.String(20), nullable=True),

        # Arm and leg
        sa.Column('arm_config', sa.String(20), nullable=True),
        sa.Column('leg_config', sa.String(20), nullable=True),

        # Metadata
        sa.Column('complexity', sa.String(20), nullable=True),
        sa.Column('risk', sa.String(20), nullable=True),
        sa.Column('customer_visible', sa.Boolean, default=True),
        sa.Column('status', sa.String(30), default='APPROVED'),
        sa.Column('version', sa.String(10), default='1.0'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_pose_geometry_family', 'pose_geometry_presets', ['family'])


def downgrade():
    op.drop_table('pose_geometry_presets')

    for col in ['body_yaw', 'body_pitch', 'body_roll', 'head_yaw', 'head_pitch', 'head_roll', 'gaze', 'expression_id']:
        op.drop_column('angle_shots', col)

    for col in ['body_yaw', 'head_yaw', 'head_pitch', 'gaze', 'expression_id']:
        op.drop_column('catalog_job_items', col)
