"""schema drift: add model columns and indexes the migration chain never created

A database built from empty with ``alembic upgrade head`` lacked columns the
models (and so every ORM query on these tables) use; databases that were built
another way, such as production, already have them. This revision adds only
what is missing, each item checked against the live table first:

* ``ghost_jobs`` and ``catalog_jobs``: ``job_id`` VARCHAR(100) with index
  ``ix_<table>_job_id``, ``quality_mode`` VARCHAR(50), ``total_skus``,
  ``completed_skus``, ``failed_skus`` INTEGER, ``meta`` JSONB.
* ``angle_shots``: ``slug`` VARCHAR(255) unique (``angle_shots_slug_key``),
  ``depth_map_url``, ``segmentation_url`` VARCHAR(500), ``camera_roll``,
  ``camera_distance``, ``crop_top``, ``crop_bottom``, ``subject_scale`` FLOAT,
  ``negative_prompt`` TEXT, ``generation_config``, ``age_groups``,
  ``gender_rules``, ``tags`` JSONB.
* ``shoot_angle_shots``: ``shoot_product_id`` VARCHAR(100) with index
  ``ix_shoot_angle_shots_shoot_product_id``.

Every column is nullable with no server default, exactly as in the models (their
defaults are Python-side), so nothing is backfilled: rows that predate a column
added here keep NULL in it. An index is skipped when any index or unique
constraint on the same column already exists, whatever its name. A ``slug``
column that exists without a unique constraint is reported and left alone
(making it unique could fail on duplicate values).

Nothing is dropped, renamed or retyped. What this revision added is recorded in
``schema_drift_additions``, and downgrade removes only those objects, so a
column the database had before this revision is never dropped by it.

Revision ID: schema_drift_001
Revises: job_refund_key_001
Create Date: 2026-10-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'schema_drift_001'
down_revision = 'job_refund_key_001'
branch_labels = None
depends_on = None

REVISION = revision
LOG = 'schema_drift_additions'


def _jsonb():
    return sa.JSON().with_variant(postgresql.JSONB(), 'postgresql')


def _job_columns():
    return [
        sa.Column('job_id', sa.String(100), nullable=True),
        sa.Column('total_skus', sa.Integer(), nullable=True),
        sa.Column('completed_skus', sa.Integer(), nullable=True),
        sa.Column('failed_skus', sa.Integer(), nullable=True),
        sa.Column('quality_mode', sa.String(50), nullable=True),
        sa.Column('meta', _jsonb(), nullable=True),
    ]


# table -> columns (in model order), then (index name, column) pairs.
COLUMNS = {
    'ghost_jobs': _job_columns(),
    'catalog_jobs': _job_columns(),
    'angle_shots': [
        sa.Column('slug', sa.String(255), nullable=True),
        sa.Column('depth_map_url', sa.String(500), nullable=True),
        sa.Column('segmentation_url', sa.String(500), nullable=True),
        sa.Column('camera_roll', sa.Float(), nullable=True),
        sa.Column('camera_distance', sa.Float(), nullable=True),
        sa.Column('crop_top', sa.Float(), nullable=True),
        sa.Column('crop_bottom', sa.Float(), nullable=True),
        sa.Column('subject_scale', sa.Float(), nullable=True),
        sa.Column('negative_prompt', sa.Text(), nullable=True),
        sa.Column('generation_config', _jsonb(), nullable=True),
        sa.Column('age_groups', _jsonb(), nullable=True),
        sa.Column('gender_rules', _jsonb(), nullable=True),
        sa.Column('tags', _jsonb(), nullable=True),
    ],
    'shoot_angle_shots': [
        sa.Column('shoot_product_id', sa.String(100), nullable=True),
    ],
}
INDEXES = [
    ('ix_ghost_jobs_job_id', 'ghost_jobs', 'job_id'),
    ('ix_catalog_jobs_job_id', 'catalog_jobs', 'job_id'),
    ('ix_shoot_angle_shots_shoot_product_id', 'shoot_angle_shots', 'shoot_product_id'),
]
SLUG_UNIQUE = ('angle_shots_slug_key', 'angle_shots', 'slug')


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table):
    return {c['name'] for c in _inspector().get_columns(table)}


def _indexed(table, column, unique=False):
    """True when an index (or unique constraint) covers exactly ``column``."""
    insp = _inspector()
    found = [i for i in insp.get_indexes(table) if i['column_names'] == [column] and (i['unique'] or not unique)]
    found += [u for u in insp.get_unique_constraints(table) if u['column_names'] == [column]]
    return bool(found)


def _log_table():
    return sa.table(
        LOG,
        sa.column('revision', sa.String),
        sa.column('object_type', sa.String),
        sa.column('table_name', sa.String),
        sa.column('object_name', sa.String),
    )


def _record(object_type, table, name):
    op.get_bind().execute(_log_table().insert().values(
        revision=REVISION, object_type=object_type, table_name=table, object_name=name,
    ))
    print(f'[migration] {REVISION}: added {object_type} {table}.{name}')


def upgrade():
    bind = op.get_bind()
    if not _inspector().has_table(LOG):
        op.create_table(
            LOG,
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('revision', sa.String(64), nullable=False),
            sa.Column('object_type', sa.String(20), nullable=False),
            sa.Column('table_name', sa.String(100), nullable=False),
            sa.Column('object_name', sa.String(100), nullable=False),
        )

    for table, columns in COLUMNS.items():
        present = _columns(table)
        for column in columns:
            if column.name not in present:
                op.add_column(table, column.copy())
                _record('column', table, column.name)

    for name, table, column in INDEXES:
        if not _indexed(table, column):
            op.create_index(name, table, [column])
            _record('index', table, name)

    name, table, column = SLUG_UNIQUE
    if not _indexed(table, column, unique=True):
        if _added(bind, 'column', table, column):
            # A column this revision just added holds only NULLs, so it can be made unique.
            if bind.dialect.name == 'postgresql':
                op.create_unique_constraint(name, table, [column])
                _record('unique', table, name)
            else:  # SQLite cannot add a constraint to an existing table; a unique index enforces the same.
                op.create_index(name, table, [column], unique=True)
                _record('index', table, name)
        else:
            print(f'[migration] {REVISION}: {table}.{column} exists without a unique constraint; '
                  'left as is (needs a duplicate check before it can be made unique)')


def _added(bind, object_type, table, name):
    log = _log_table()
    return bind.execute(sa.select(log.c.object_name).where(
        log.c.revision == REVISION, log.c.object_type == object_type,
        log.c.table_name == table, log.c.object_name == name,
    )).first() is not None


def downgrade():
    bind = op.get_bind()
    if not _inspector().has_table(LOG):
        return
    log = _log_table()
    added = bind.execute(sa.select(log.c.object_type, log.c.table_name, log.c.object_name)
                         .where(log.c.revision == REVISION)).all()

    for object_type, table, name in added:
        if object_type == 'unique':
            op.drop_constraint(name, table, type_='unique')
        elif object_type == 'index':
            op.drop_index(name, table_name=table)

    dropped = {}
    for object_type, table, name in added:
        if object_type == 'column':
            dropped.setdefault(table, []).append(name)
    for table, names in dropped.items():
        with op.batch_alter_table(table) as batch:
            for name in names:
                batch.drop_column(name)

    bind.execute(log.delete().where(log.c.revision == REVISION))
    if bind.execute(sa.select(sa.func.count()).select_from(log)).scalar() == 0:
        op.drop_table(LOG)
