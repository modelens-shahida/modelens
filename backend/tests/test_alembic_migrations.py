"""Alembic revision graph and the re-runnable create_table guard.

No Postgres needed: the graph is read from the migration files, and the guard
runs against an in-memory SQLite database.
"""
import os

import pytest
import sqlalchemy as sa
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory

from app.migration_guard import SchemaMismatch, create_table_if_absent, table_differences

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def script():
    cfg = Config(os.path.join(BACKEND, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND, "alembic"))
    return ScriptDirectory.from_config(cfg)


def test_single_head(script):
    assert len(script.get_heads()) == 1, f"multiple Alembic heads: {script.get_heads()}"


def test_every_down_revision_exists(script):
    known = {rev.revision for rev in script.walk_revisions()}
    for rev in script.walk_revisions():
        for parent in rev._all_down_revisions:
            assert parent in known, f"{rev.revision} revises missing revision {parent}"


def test_history_is_linear_from_a_single_base(script):
    assert len(script.get_bases()) == 1
    for rev in script.walk_revisions():
        assert len(rev.nextrev) <= 1, f"{rev.revision} branches into {rev.nextrev}"


def test_brand_sso_revision_is_in_the_chain(script):
    # Local DBs are stamped with it; it must stay resolvable.
    rev = script.get_revision("brand_sso_001")
    assert rev.down_revision == "add_invitations_table"
    assert "architecture_v1_001" in rev.nextrev


def _columns():
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    ]


@pytest.fixture
def ops():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            yield conn
    engine.dispose()


def test_guard_creates_missing_table(ops):
    create_table_if_absent("things", *_columns())
    assert sa.inspect(ops).has_table("things")


def test_guard_skips_existing_matching_table(ops):
    create_table_if_absent("things", *_columns())
    ops.execute(sa.text("INSERT INTO things (id, name) VALUES (1, 'kept')"))
    create_table_if_absent("things", *_columns())
    assert ops.execute(sa.text("SELECT name FROM things")).scalar_one() == "kept"


@pytest.mark.parametrize("live, expected_problem", [
    ([sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("name", sa.String(255), nullable=False)], "missing column notes"),
    (_columns() + [sa.Column("extra", sa.Integer())], "unexpected column extra"),
    ([sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("name", sa.String(100), nullable=False),
      sa.Column("notes", sa.Text())], "name: type is VARCHAR(100), expected VARCHAR(255)"),
    ([sa.Column("id", sa.Integer(), primary_key=True),
      sa.Column("name", sa.String(255), nullable=True),
      sa.Column("notes", sa.Text())], "name: nullable is True, expected False"),
])
def test_guard_refuses_differing_table(ops, live, expected_problem):
    sa.Table("things", sa.MetaData(), *live).create(ops)
    assert expected_problem in table_differences(ops, "things", _columns())
    with pytest.raises(SchemaMismatch, match="does not match this migration"):
        create_table_if_absent("things", *_columns())
