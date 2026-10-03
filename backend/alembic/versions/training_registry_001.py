"""training registry - extend P3 datasets/experiment_runs/model_artifacts; add exports, checkpoints, evaluations, promotions

Extends the P3 registry instead of duplicating it:
  * datasets          (TrainingDataset): + dataset_version, character_version
  * experiment_runs   (TrainingRun):     + character_version, trainer, seed, manifests, metrics, ...
  * model_artifacts   (Adapter):         + layer, kind, character_version, checkpoint_id, reference
New tables: training_exports, training_checkpoints, evaluation_runs, runtime_promotions.

Nothing here touches character_registry_versions. Safe to run twice.

Revision ID: training_registry_001
Revises: character_version_registry_001
Create Date: 2026-10-03
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'training_registry_001'
down_revision = 'character_version_registry_001'
branch_labels = None
depends_on = None


def _added_columns():
    return {
        'datasets': [
            sa.Column('dataset_version', sa.String(20), nullable=True),
            sa.Column('character_version', sa.String(10), nullable=True),
        ],
        'experiment_runs': [
            sa.Column('character_version', sa.String(10), nullable=True),
            sa.Column('dataset_version', sa.String(20), nullable=True),
            sa.Column('export_id', sa.String(50), nullable=True),
            sa.Column('trainer', sa.String(50), nullable=True),
            sa.Column('trainer_version', sa.String(30), nullable=True),
            sa.Column('seed', sa.BigInteger, nullable=True),
            sa.Column('image_manifest', JSONB, nullable=True),
            sa.Column('caption_manifest', JSONB, nullable=True),
            sa.Column('bucket_configuration', JSONB, nullable=True),
            sa.Column('training_metrics', JSONB, nullable=True),
            sa.Column('evaluation_result', JSONB, nullable=True),
            sa.Column('artifact_hash', sa.String(64), nullable=True),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        ],
        'model_artifacts': [
            sa.Column('layer', sa.String(20), nullable=True),
            sa.Column('kind', sa.String(20), nullable=True),
            sa.Column('character_version', sa.String(10), nullable=True),
            sa.Column('checkpoint_id', sa.String(50), nullable=True),
            sa.Column('reference', JSONB, nullable=True),
            sa.Column('created_by', sa.String(100), nullable=True),
        ],
    }


def _new_tables():
    return {
        'training_exports': [
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('export_id', sa.String(50), unique=True, nullable=False),
            sa.Column('dataset_id', sa.String(50), nullable=False, index=True),
            sa.Column('dataset_version', sa.String(20), nullable=True),
            sa.Column('export_format', sa.String(30), nullable=False),
            sa.Column('storage_path', sa.String(500), nullable=False),
            sa.Column('image_manifest', JSONB, nullable=True),
            sa.Column('caption_manifest', JSONB, nullable=True),
            sa.Column('bucket_configuration', JSONB, nullable=True),
            sa.Column('item_count', sa.Integer, server_default='0'),
            sa.Column('artifact_hash', sa.String(64), nullable=False),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        ],
        'training_checkpoints': [
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('checkpoint_id', sa.String(50), unique=True, nullable=False),
            sa.Column('run_id', sa.String(50), nullable=False, index=True),
            sa.Column('step', sa.Integer, nullable=True),
            sa.Column('epoch', sa.Integer, nullable=True),
            sa.Column('storage_path', sa.String(500), nullable=False),
            sa.Column('checksum_sha256', sa.String(64), nullable=False),
            sa.Column('file_size_bytes', sa.BigInteger, nullable=True),
            sa.Column('metrics', JSONB, nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        ],
        'evaluation_runs': [
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('evaluation_id', sa.String(50), unique=True, nullable=False),
            sa.Column('run_id', sa.String(50), nullable=False, index=True),
            sa.Column('checkpoint_id', sa.String(50), nullable=True),
            sa.Column('evaluator', sa.String(100), nullable=False),
            sa.Column('evaluator_version', sa.String(30), nullable=True),
            sa.Column('qa_profile_id', sa.String(100), nullable=True),
            sa.Column('score', sa.Float, nullable=True),
            sa.Column('decision', sa.String(10), nullable=False),
            sa.Column('metrics', JSONB, nullable=True),
            sa.Column('report_path', sa.String(500), nullable=True),
            sa.Column('created_by', sa.String(100), nullable=True),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        ],
        'runtime_promotions': [
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('promotion_id', sa.String(50), unique=True, nullable=False),
            sa.Column('run_id', sa.String(50), nullable=False, index=True),
            sa.Column('adapter_id', sa.String(50), nullable=False),
            sa.Column('checkpoint_id', sa.String(50), nullable=True),
            sa.Column('character_id', sa.String(50), nullable=False),
            sa.Column('character_version', sa.String(10), nullable=False),
            sa.Column('production_alias', sa.String(100), nullable=True),
            sa.Column('promoted_by', sa.String(100), nullable=False),
            sa.Column('promoted_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column('notes', sa.Text, nullable=True),
        ],
    }


INDEXES = [
    ('ix_experiment_runs_character_version', 'experiment_runs', ['character_id', 'character_version']),
    ('ix_model_artifacts_character_layer', 'model_artifacts', ['character_id', 'character_version', 'layer']),
]


def upgrade():
    inspector = sa.inspect(op.get_bind())

    for table, columns in _added_columns().items():
        existing = {c['name'] for c in inspector.get_columns(table)}
        for col in columns:
            if col.name not in existing:
                op.add_column(table, col)

    for table, columns in _new_tables().items():
        if not inspector.has_table(table):
            op.create_table(table, *columns)

    for name, table, columns in INDEXES:
        if name not in {i['name'] for i in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    for name, table, _ in INDEXES:
        if name in {i['name'] for i in inspector.get_indexes(table)}:
            op.drop_index(name, table_name=table)
    for table in reversed(list(_new_tables())):
        if inspector.has_table(table):
            op.drop_table(table)
    for table, columns in _added_columns().items():
        existing = {c['name'] for c in inspector.get_columns(table)}
        for col in columns:
            if col.name in existing:
                op.drop_column(table, col.name)
