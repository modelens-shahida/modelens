"""Guards on the older migrations (workspace_isolation_001 ... character_registry_v2_001): objects that
already exist are skipped when they match, and the upgrade stops (SchemaMismatch) when they differ.
SQLite, no Postgres needed: each migration's upgrade() runs on a database that already has every model
table (as production, partly built from the models), then once more."""
import importlib.util
import os

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

import app.models.db as models
from app.migration_guard import SchemaMismatch, add_column_if_absent, create_index_if_absent, ensure_table

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARDED = ("workspace_isolation_001", "character_registry_001", "provider_abstraction_001",
           "pose_geometry_separation_001", "credit_ledger_001", "dataset_registry_001", "character_registry_v2_001")


def _module(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(BACKEND, "alembic", "versions", f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ops(engine, fn):
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            return fn()


@pytest.fixture
def db(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'g.db'}")
    yield engine
    engine.dispose()


def test_guards_skip_matching_objects_and_create_missing_ones(db):
    _ops(db, lambda: ensure_table("t", sa.Column("id", sa.Integer, primary_key=True), sa.Column("a", sa.String(10))))
    _ops(db, lambda: ensure_table("t", sa.Column("id", sa.Integer, primary_key=True)))  # extra live column: fine
    _ops(db, lambda: add_column_if_absent("t", sa.Column("b", sa.Integer)))
    _ops(db, lambda: add_column_if_absent("t", sa.Column("b", sa.Integer)))  # second time: skipped
    _ops(db, lambda: create_index_if_absent("ix_t_a", "t", ["a"]))
    _ops(db, lambda: create_index_if_absent("ix_t_a", "t", ["a"]))
    with db.connect() as conn:
        assert {c["name"] for c in sa.inspect(conn).get_columns("t")} == {"id", "a", "b"}


@pytest.mark.parametrize("step", [
    lambda: add_column_if_absent("t", sa.Column("a", sa.Integer)),  # exists with another type
    lambda: ensure_table("t", sa.Column("id", sa.Integer, primary_key=True), sa.Column("missing", sa.Integer)),
    lambda: create_index_if_absent("ix_t_a", "t", ["id"]),  # same name, other columns
])
def test_guards_stop_on_a_different_existing_object(db, step):
    _ops(db, lambda: ensure_table("t", sa.Column("id", sa.Integer, primary_key=True), sa.Column("a", sa.String(10))))
    _ops(db, lambda: create_index_if_absent("ix_t_a", "t", ["a"]))
    with pytest.raises(SchemaMismatch):
        _ops(db, step)


@pytest.mark.parametrize("name", GUARDED)
def test_old_migration_skips_objects_the_models_already_built(db, name):
    models.Base.metadata.create_all(db)  # every model table, as production may have them
    module = _module(name)
    try:
        _ops(db, module.upgrade)
    except SchemaMismatch as exc:  # a real difference: reported, never "already exists"
        pytest.fail(f"{name}: {exc}")
    _ops(db, module.upgrade)  # and again: nothing left to do


def test_no_guarded_migration_calls_op_directly():
    for name in GUARDED:
        with open(os.path.join(BACKEND, "alembic", "versions", f"{name}.py")) as fh:
            body = fh.read().split("def upgrade", 1)[1].split("def downgrade", 1)[0]
        for call in ("op.add_column(", "op.create_table(", "op.create_index("):
            assert call not in body, (name, call)
