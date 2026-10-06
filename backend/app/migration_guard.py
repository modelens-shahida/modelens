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
