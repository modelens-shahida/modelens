"""dataset registry - Dataset, DatasetItem, DatasetAnnotation, ExperimentRun, ExperimentMetric, ModelArtifact, Rights Registry

Revision ID: dataset_registry_001
Revises: credit_ledger_001
Create Date: 2026-09-15
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'dataset_registry_001'
down_revision = 'credit_ledger_001'
branch_labels = None
depends_on = None


def upgrade():
    # Dataset table
    op.create_table('datasets',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('dataset_id', sa.String(50), unique=True, nullable=False),
        sa.Column('character_id', sa.String(50), nullable=True),
        sa.Column('workspace_id', sa.String(50), nullable=True),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('purpose', sa.String(30), nullable=False),
        sa.Column('split', sa.String(20), default='TRAIN'),
        sa.Column('status', sa.String(30), default='DRAFT'),
        sa.Column('total_items', sa.Integer, default=0),
        sa.Column('frozen', sa.Boolean, default=False),
        sa.Column('frozen_at', sa.DateTime, nullable=True),
        sa.Column('manifest', JSONB, nullable=True),
        sa.Column('rights_snapshot', JSONB, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_datasets_character_id', 'datasets', ['character_id'])
    op.create_index('ix_datasets_workspace_id', 'datasets', ['workspace_id'])

    # Dataset Item table
    op.create_table('dataset_items',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('dataset_id', sa.String(50), nullable=False),
        sa.Column('asset_id', sa.Integer, nullable=True),
        sa.Column('asset_version', sa.Integer, default=1),
        sa.Column('split', sa.String(20), default='TRAIN'),
        sa.Column('sample_weight', sa.Float, default=1.0),
        sa.Column('training_eligible', sa.Boolean, default=True),
        sa.Column('training_permission', sa.String(20), default='ALLOWED'),
        sa.Column('caption', sa.Text, nullable=True),
        sa.Column('caption_version', sa.Integer, default=1),
        sa.Column('status', sa.String(20), default='APPROVED'),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_dataset_items_dataset_id', 'dataset_items', ['dataset_id'])
    op.create_index('ix_dataset_items_asset_id', 'dataset_items', ['asset_id'])

    # Dataset Annotation table
    op.create_table('dataset_annotations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('dataset_item_id', sa.Integer, nullable=False),
        sa.Column('annotation_type', sa.String(50), nullable=False),
        sa.Column('annotation_data', JSONB, nullable=True),
        sa.Column('annotated_by', sa.String(50), nullable=True),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_dataset_annotations_item_id', 'dataset_annotations', ['dataset_item_id'])

    # Experiment Run table
    op.create_table('experiment_runs',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('run_id', sa.String(50), unique=True, nullable=False),
        sa.Column('experiment_name', sa.String(100), nullable=False),
        sa.Column('character_id', sa.String(50), nullable=True),
        sa.Column('dataset_id', sa.String(50), nullable=True),
        sa.Column('base_model', sa.String(100), nullable=True),
        sa.Column('adapter_type', sa.String(50), nullable=True),
        sa.Column('training_token', sa.String(50), nullable=True),
        sa.Column('status', sa.String(30), default='QUEUED'),
        sa.Column('mlflow_run_id', sa.String(100), nullable=True),
        sa.Column('mlflow_experiment_id', sa.String(100), nullable=True),
        sa.Column('hyperparameters', JSONB, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_experiment_runs_character_id', 'experiment_runs', ['character_id'])

    # Experiment Metric table
    op.create_table('experiment_metrics',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('run_id', sa.String(50), nullable=False),
        sa.Column('metric_name', sa.String(50), nullable=False),
        sa.Column('metric_value', sa.Float, nullable=False),
        sa.Column('step', sa.Integer, nullable=True),
        sa.Column('epoch', sa.Integer, nullable=True),
        sa.Column('recorded_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_experiment_metrics_run_id', 'experiment_metrics', ['run_id'])

    # Model Artifact table
    op.create_table('model_artifacts',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('model_id', sa.String(50), unique=True, nullable=False),
        sa.Column('run_id', sa.String(50), nullable=True),
        sa.Column('character_id', sa.String(50), nullable=True),
        sa.Column('dataset_id', sa.String(50), nullable=True),
        sa.Column('adapter_type', sa.String(50), nullable=True),
        sa.Column('base_model', sa.String(100), nullable=True),
        sa.Column('storage_path', sa.String(500), nullable=True),
        sa.Column('checksum_sha256', sa.String(64), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger, nullable=True),
        sa.Column('status', sa.String(30), default='EXPERIMENTAL'),
        sa.Column('production_alias', sa.String(100), nullable=True),
        sa.Column('version_major', sa.Integer, default=1),
        sa.Column('version_minor', sa.Integer, default=0),
        sa.Column('supersedes_model_id', sa.String(50), nullable=True),
        sa.Column('identity_score', sa.Float, nullable=True),
        sa.Column('qa_score', sa.Float, nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_model_artifacts_character_id', 'model_artifacts', ['character_id'])
    op.create_index('ix_model_artifacts_status', 'model_artifacts', ['status'])

    # Rights Registry table
    op.create_table('rights_registry',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('rights_id', sa.String(50), unique=True, nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', sa.String(100), nullable=False),
        sa.Column('workspace_id', sa.String(50), nullable=True),
        sa.Column('ownership_status', sa.String(30), default='OWN-UNKNOWN'),
        sa.Column('source_type', sa.String(30), default='SRC-UNKNOWN'),
        sa.Column('generation_allowed', sa.Boolean, default=True),
        sa.Column('commercial_allowed', sa.Boolean, default=True),
        sa.Column('publication_allowed', sa.Boolean, default=True),
        sa.Column('training_allowed', sa.Boolean, default=False),
        sa.Column('internal_improvement_allowed', sa.Boolean, default=False),
        sa.Column('consent_status', sa.String(30), default='CONSENT-PENDING'),
        sa.Column('rights_status', sa.String(30), default='RIGHTS-UNKNOWN'),
        sa.Column('license_id', sa.String(50), nullable=True),
        sa.Column('expiration_date', sa.DateTime, nullable=True),
        sa.Column('evidence_reference', sa.String(200), nullable=True),
        sa.Column('meta', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_rights_registry_resource', 'rights_registry', ['resource_type', 'resource_id'])
    op.create_index('ix_rights_registry_workspace', 'rights_registry', ['workspace_id'])


def downgrade():
    op.drop_table('rights_registry')
    op.drop_table('model_artifacts')
    op.drop_table('experiment_metrics')
    op.drop_table('experiment_runs')
    op.drop_table('dataset_annotations')
    op.drop_table('dataset_items')
    op.drop_table('datasets')
