"""Migration schema_drift_001.

On a database built by the migration chain (the model columns it
never created are missing) it adds exactly the model's columns and indexes; on
a database that already has them (production) it changes nothing; downgrade
removes only what the upgrade added. Runs against SQLite; the same checks were
run by hand against Postgres 16 (see the PR).

No network: SQLite only.
"""
import importlib.util
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from app.migration_guard import table_differences
from app.models.db import Base

pytestmark = pytest.mark.integration  # runs a migration

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATION = os.path.join(BACKEND, "alembic", "versions", "schema_drift_001.py")

# What the migration chain never created: table -> columns, plus the model's indexes on them.
DRIFT = {
    "ghost_jobs": ["job_id", "total_skus", "completed_skus", "failed_skus", "quality_mode", "meta"],
    "catalog_jobs": ["job_id", "total_skus", "completed_skus", "failed_skus", "quality_mode", "meta"],
    "angle_shots": ["slug", "depth_map_url", "segmentation_url", "camera_roll", "camera_distance", "crop_top",
                    "crop_bottom", "subject_scale", "negative_prompt", "generation_config", "age_groups",
                    "gender_rules", "tags"],
    "shoot_angle_shots": ["shoot_product_id"],
}
DRIFT_INDEXES = {
    "ghost_jobs": "ix_ghost_jobs_job_id",
    "catalog_jobs": "ix_catalog_jobs_job_id",
    "shoot_angle_shots": "ix_shoot_angle_shots_shoot_product_id",
}


# ========================== Migration schema_drift_001 ==========================

def _migration():
    spec = importlib.util.spec_from_file_location("schema_drift_001", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _build(engine, missing):
    """The four tables as the models define them (foreign keys left out), without ``missing`` columns."""
    metadata = sa.MetaData()
    for name in DRIFT:
        model = Base.metadata.tables[name]
        skip = set(missing.get(name, ()))
        columns = [sa.Column(c.name, c.type, primary_key=c.primary_key, nullable=c.nullable, unique=c.unique)
                   for c in model.columns if c.name not in skip]
        table = sa.Table(name, metadata, *columns)
        for index in model.indexes:
            if not {c.name for c in index.columns} & skip:
                sa.Index(index.name, *[table.c[c.name] for c in index.columns], unique=index.unique)
    metadata.create_all(engine)


@pytest.fixture
def chain_db(tmp_path):
    """Like a database built from empty by the migration chain: the drift columns are missing."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'chain.db'}")
    _build(engine, DRIFT)
    yield engine
    engine.dispose()


@pytest.fixture
def model_db(tmp_path):
    """Like production: every model column and index is already there."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'model.db'}")
    _build(engine, {})
    yield engine
    engine.dispose()


def _run(engine, step):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            getattr(_migration(), step)()


def _schema(engine):
    with engine.connect() as conn:
        inspector = sa.inspect(conn)
        return {
            "tables": set(inspector.get_table_names()),
            **{name: ({c["name"] for c in inspector.get_columns(name)},
                      {i["name"] for i in inspector.get_indexes(name)}) for name in DRIFT},
        }


def _differences(engine):
    with engine.connect() as conn:
        return {name: table_differences(conn, name, list(Base.metadata.tables[name].columns)) for name in DRIFT}


def _insert(engine, table, **values):
    """Insert a row into whatever columns the live table has, NOT NULL ones filled from the model's defaults."""
    model = Base.metadata.tables[table]
    with engine.begin() as conn:
        live = {c["name"] for c in sa.inspect(conn).get_columns(table)}
        row = {}
        for c in model.columns:
            if c.name in live and c.default is not None and not c.primary_key:
                row[c.name] = c.default.arg(None) if c.default.is_callable else c.default.arg
        row.update(values)
        conn.execute(sa.table(table, *[sa.column(k) for k in row]).insert().values(**row))


def _added(engine):
    with engine.connect() as conn:
        if not sa.inspect(conn).has_table("schema_drift_additions"):
            return None
        return set(conn.exec_driver_sql(
            "SELECT object_type, table_name, object_name FROM schema_drift_additions").all())


def test_migration_revises_the_single_previous_head():
    module = _migration()
    assert (module.revision, module.down_revision) == ("schema_drift_001", "job_refund_key_001")


def test_upgrade_on_a_chain_built_db_adds_exactly_the_model_columns_and_indexes(chain_db):
    assert all(_differences(chain_db).values())  # the drift is there to begin with
    _run(chain_db, "upgrade")
    assert _differences(chain_db) == {name: [] for name in DRIFT}  # names, types, nullability
    schema = _schema(chain_db)
    for table, index in DRIFT_INDEXES.items():
        assert index in schema[table][1]
    expected = {("column", t, c) for t, cols in DRIFT.items() for c in cols}
    expected |= {("index", t, i) for t, i in DRIFT_INDEXES.items()} | {("index", "angle_shots", "angle_shots_slug_key")}
    assert _added(chain_db) == expected
    for name, slug in (("a", None), ("b", None), ("c", "front")):  # slug is unique, NULLs allowed
        _insert(chain_db, "angle_shots", name=name, slug=slug)
    with pytest.raises(IntegrityError):
        _insert(chain_db, "angle_shots", name="d", slug="front")


def test_rows_from_before_the_upgrade_keep_null_in_new_columns(chain_db):
    _insert(chain_db, "ghost_jobs", id=1, user_id=1, brand_id=1, status="completed")
    _run(chain_db, "upgrade")
    with chain_db.connect() as conn:
        row = conn.exec_driver_sql("SELECT status, job_id, total_skus, meta FROM ghost_jobs WHERE id = 1").one()
    assert tuple(row) == ("completed", None, None, None)  # nothing guessed


def test_upgrade_where_everything_exists_is_a_no_op_and_downgrade_keeps_it(model_db):
    _insert(model_db, "ghost_jobs", id=1, user_id=1, brand_id=1, job_id="prod-job")
    before = _schema(model_db)
    _run(model_db, "upgrade")
    assert _added(model_db) == set()
    after = _schema(model_db)
    assert after == {**before, "tables": before["tables"] | {"schema_drift_additions"}}
    _run(model_db, "downgrade")
    assert _schema(model_db) == before  # the bookkeeping table goes, production's columns stay
    with model_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT job_id FROM ghost_jobs").scalar_one() == "prod-job"


def test_existing_job_id_is_left_alone_and_downgrade_removes_only_what_was_added(chain_db):
    with chain_db.begin() as conn:  # production-like: job_id and its index exist, the rest is missing
        conn.exec_driver_sql("ALTER TABLE ghost_jobs ADD COLUMN job_id VARCHAR(100)")
        conn.exec_driver_sql("CREATE INDEX ix_ghost_jobs_job_id ON ghost_jobs (job_id)")
    _insert(chain_db, "ghost_jobs", id=1, user_id=1, brand_id=1, job_id="prod-job")
    _run(chain_db, "upgrade")
    added = _added(chain_db)
    assert ("column", "ghost_jobs", "job_id") not in added
    assert ("index", "ghost_jobs", "ix_ghost_jobs_job_id") not in added
    assert ("column", "ghost_jobs", "meta") in added
    _run(chain_db, "downgrade")
    columns, indexes = _schema(chain_db)["ghost_jobs"]
    assert "job_id" in columns and "ix_ghost_jobs_job_id" in indexes
    assert not {"total_skus", "completed_skus", "failed_skus", "quality_mode", "meta"} & columns
    assert "schema_drift_additions" not in _schema(chain_db)["tables"]
    with chain_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT job_id FROM ghost_jobs").scalar_one() == "prod-job"


def test_an_index_on_the_column_under_another_name_is_not_duplicated(chain_db):
    with chain_db.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE ghost_jobs ADD COLUMN job_id VARCHAR(100)")
        conn.exec_driver_sql("CREATE INDEX idx_ghost_jobs_job_id ON ghost_jobs (job_id)")
    _run(chain_db, "upgrade")
    indexes = _schema(chain_db)["ghost_jobs"][1]
    assert "idx_ghost_jobs_job_id" in indexes and "ix_ghost_jobs_job_id" not in indexes


def test_an_existing_slug_without_a_unique_constraint_is_not_made_unique(chain_db):
    with chain_db.begin() as conn:
        conn.exec_driver_sql("ALTER TABLE angle_shots ADD COLUMN slug VARCHAR(255)")
    _insert(chain_db, "angle_shots", name="a", slug="dup")
    _insert(chain_db, "angle_shots", name="b", slug="dup")
    _run(chain_db, "upgrade")
    assert not {row for row in _added(chain_db) if row[1] == "angle_shots" and row[2] in ("slug", "angle_shots_slug_key")}
    with chain_db.connect() as conn:
        assert conn.exec_driver_sql("SELECT COUNT(*) FROM angle_shots WHERE slug = 'dup'").scalar_one() == 2


def test_downgrade_upgrade_round_trip(chain_db):
    before = _schema(chain_db)
    _run(chain_db, "upgrade")
    upgraded = _schema(chain_db)
    _run(chain_db, "downgrade")
    assert _schema(chain_db) == before
    _run(chain_db, "upgrade")
    assert _schema(chain_db) == upgraded
    assert _differences(chain_db) == {name: [] for name in DRIFT}


def test_upgrade_twice_adds_nothing_the_second_time(chain_db):
    _run(chain_db, "upgrade")
    once, added = _schema(chain_db), _added(chain_db)
    _run(chain_db, "upgrade")
    assert (_schema(chain_db), _added(chain_db)) == (once, added)
