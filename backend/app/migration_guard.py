"""Re-runnable table creation for Alembic migrations.

Some local databases have tables from migrations whose revision was never
recorded in ``alembic_version`` (the schema is ahead of the record). Running
``alembic upgrade head`` then fails with ``DuplicateTableError``.

``create_table_if_absent`` is a drop-in for ``op.create_table``: it creates the
table when it is missing, and when it already exists it checks that the live
columns match what the migration defines. A match means that migration's work
is already done, so it is skipped and Alembic records the revision as usual.
Any difference aborts the upgrade with a ``SchemaMismatch`` listing every
difference, so a half-built or diverged table is never silently accepted.
"""
import sqlalchemy as sa
from alembic import op

# Key of the Postgres advisory lock held while migrations run (any constant
# bigint; only migrations use it).
MIGRATION_LOCK_KEY = 720_161_001  # fits 32 bits: pg_locks shows it as objid

# Types that the database reports differently from how they are declared.
_TYPE_ALIASES = {
    "FLOAT": "DOUBLE PRECISION",
}


class SchemaMismatch(RuntimeError):
    pass


def _type_name(type_, dialect):
    name = type_.compile(dialect=dialect).upper()
    return _TYPE_ALIASES.get(name, name)


def table_differences(bind, name, columns):
    """Differences between a live table and the columns a migration expects."""
    dialect = bind.dialect
    live = {c["name"]: c for c in sa.inspect(bind).get_columns(name)}
    expected = {c.name: c for c in columns}
    problems = []
    for col in sorted(set(expected) - set(live)):
        problems.append(f"missing column {col}")
    for col in sorted(set(live) - set(expected)):
        problems.append(f"unexpected column {col}")
    for col_name in sorted(set(expected) & set(live)):
        want, have = expected[col_name], live[col_name]
        want_type = _type_name(want.type, dialect)
        have_type = _type_name(have["type"], dialect)
        if want_type != have_type:
            problems.append(f"{col_name}: type is {have_type}, expected {want_type}")
        want_nullable = bool(want.nullable) and not want.primary_key
        if bool(have["nullable"]) != want_nullable:
            problems.append(
                f"{col_name}: nullable is {have['nullable']}, expected {want_nullable}"
            )
    return problems


def create_table_if_absent(name, *elements, **kw):
    """``op.create_table`` that skips a table already present with the same columns."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(name):
        return op.create_table(name, *elements, **kw)
    columns = [e for e in elements if isinstance(e, sa.Column)]
    problems = table_differences(bind, name, columns)
    if problems:
        raise SchemaMismatch(
            f"Table '{name}' already exists but does not match this migration: "
            + "; ".join(problems)
            + ". Not skipping it. See 'If local migrations fail' in README.md."
        )
    print(f"[migration] table {name} already exists with matching columns; skipping create")
    return None


def take_migration_lock(connection) -> bool:
    """Serialize concurrent ``alembic upgrade`` runs (e.g. two replicas starting at once).

    Call inside the migration transaction, before the migrations run. On Postgres
    this waits for ``pg_advisory_xact_lock``, which is released when that
    transaction commits or rolls back; the second runner then reads the
    committed ``alembic_version`` and has nothing left to do. Other databases
    (SQLite in tests) need no lock. Returns whether a lock was taken.
    """
    if connection.dialect.name != "postgresql":
        return False
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK_KEY})
    return True


# ---------------------------------------------------------------------------
# Guards for the older migrations that used plain op.add_column / op.create_table /
# op.create_index (workspace_isolation_001 ... character_registry_v2_001). Production
# was partly built outside Alembic, so some of their objects may already exist.
# Each helper skips an object that already exists as the migration defines it and
# stops the upgrade (SchemaMismatch, nothing changed: one transaction) when it exists
# differently. A table may have *extra* columns (later migrations and the models add
# some); missing columns or other types stop the upgrade.


def _column_problems(bind, table, column):
    live = {c["name"]: c for c in sa.inspect(bind).get_columns(table)}
    if column.name not in live:
        return None  # absent
    want = _type_name(column.type, bind.dialect)
    have = _type_name(live[column.name]["type"], bind.dialect)
    return [] if want == have else [f"{table}.{column.name}: type is {have}, expected {want}"]


def add_column_if_absent(table, column):
    """``op.add_column`` that skips a column already present with the same type."""
    bind = op.get_bind()
    problems = _column_problems(bind, table, column)
    if problems is None:
        return op.add_column(table, column)
    if problems:
        raise SchemaMismatch("; ".join(problems) + ". Not skipping it.")
    print(f"[migration] column {table}.{column.name} already exists; skipping add")
    return None


def ensure_table(name, *elements, **kw):
    """``op.create_table`` that skips a table already present with at least these columns
    (same types); extra live columns are allowed."""
    bind = op.get_bind()
    if not sa.inspect(bind).has_table(name):
        return op.create_table(name, *elements, **kw)
    problems = []
    for column in (e for e in elements if isinstance(e, sa.Column)):
        found = _column_problems(bind, name, column)
        problems.extend([f"missing column {column.name}"] if found is None else found)
    if problems:
        raise SchemaMismatch(f"Table '{name}' already exists but does not match this migration: "
                             + "; ".join(problems) + ". Not skipping it.")
    print(f"[migration] table {name} already exists with the expected columns; skipping create")
    return None


def create_index_if_absent(name, table, columns, **kw):
    """``op.create_index`` that skips an index of that name already on the same columns."""
    bind = op.get_bind()
    existing = {ix["name"]: ix for ix in sa.inspect(bind).get_indexes(table)}
    if name not in existing:
        return op.create_index(name, table, columns, **kw)
    if list(existing[name]["column_names"]) != list(columns):
        raise SchemaMismatch(f"Index '{name}' on {table} exists on {existing[name]['column_names']}, "
                             f"expected {list(columns)}. Not skipping it.")
    print(f"[migration] index {name} already exists; skipping create")
    return None
