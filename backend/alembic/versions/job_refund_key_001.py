"""refund key on the credit ledger: each job is refunded at most once

* ``credit_transactions.refund_key``: nullable, unique index
  ``ix_credit_transactions_refund_key``. app/services/job_refunds.py writes it
  on every refund row (``ghost_job:12``, ``generation:gen_abc``, ...), so the
  database itself refuses a second refund for the same job. NULL for every
  other row.
* Backfill: refund rows written before this revision get their key where the
  row says unambiguously what it refunded:

  - AIJob worker refunds (``reference_type = 'job'``): ``job:<id>``
  - reservation refunds by credits_sync_service (``reference_id =
    'refund_<generation id>'``): ``generation:<generation id>``
  - NestJS fail callback refunds (``description = 'Generation failed refund -
    <generation id>'``): ``generation:<generation id>``
  - NestJS partial refunds (``description = 'Partial refund for generation
    <generation id>'``): ``generation:<generation id>:partial``

  Ghost, sketch and catalog refunds never wrote a ledger row, so there is
  nothing of theirs to backfill. If two rows would get the same key (a job
  refunded twice), the upgrade stops before changing anything and lists them;
  nothing is deleted.

Columns and indexes are only added when missing: safe to run twice.

Revision ID: job_refund_key_001
Revises: stripe_customer_ledger_001
Create Date: 2026-10-15
"""
from alembic import op
import sqlalchemy as sa

revision = 'job_refund_key_001'
down_revision = 'stripe_customer_ledger_001'
branch_labels = None
depends_on = None

LEDGER = 'credit_transactions'
INDEX = 'ix_credit_transactions_refund_key'

# The key each pre-existing refund row gets (NULL: left without one). Postgres and SQLite.
BACKFILL_KEY = (
    "CASE WHEN transaction_type <> 'refund' OR reference_id IS NULL THEN NULL "
    "WHEN reference_type = 'job' THEN 'job:' || reference_id "
    "WHEN substr(reference_id, 1, 7) = 'refund_' THEN 'generation:' || substr(reference_id, 8) "
    "WHEN description = 'Generation failed refund - ' || reference_id THEN 'generation:' || reference_id "
    "WHEN description = 'Partial refund for generation ' || reference_id "
    "THEN 'generation:' || reference_id || ':' || 'partial' "  # ':partial' would read as a bind parameter
    "END"
)


class DuplicateRefunds(RuntimeError):
    pass


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table):
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _duplicate_refunds(bind):
    """Refund keys that would appear on more than one row once backfilled."""
    key = BACKFILL_KEY
    if 'refund_key' in _columns(LEDGER):
        key = f"COALESCE(refund_key, {BACKFILL_KEY})"
    return bind.execute(sa.text(
        f"SELECT k, COUNT(*) AS n, SUM(amount) AS credits FROM (SELECT {key} AS k, amount FROM credit_transactions) "
        "AS refunds WHERE k IS NOT NULL GROUP BY k HAVING COUNT(*) > 1 ORDER BY k"
    )).all()


def upgrade():
    bind = op.get_bind()

    # Checked before any schema change, so a stopped upgrade leaves nothing behind
    # (SQLite does not roll back DDL the way Postgres does).
    duplicates = _duplicate_refunds(bind)
    if duplicates:
        listed = ', '.join(f'{key} ({n} rows, {credits} credits)' for key, n, credits in duplicates)
        raise DuplicateRefunds(
            f'credit_transactions has jobs that were refunded more than once: {listed}. '
            'The upgrade was stopped before changing anything and nothing was deleted. '
            'Review these rows (and the extra credits they returned) with the team, then re-run the upgrade.'
        )

    if 'refund_key' not in _columns(LEDGER):
        op.add_column(LEDGER, sa.Column('refund_key', sa.String(255), nullable=True))
    bind.execute(sa.text(
        f"UPDATE credit_transactions SET refund_key = {BACKFILL_KEY} "
        "WHERE refund_key IS NULL AND transaction_type = 'refund'"
    ))
    if INDEX not in _indexes(LEDGER):
        op.create_index(INDEX, LEDGER, ['refund_key'], unique=True)


def downgrade():
    # Refund rows keep reference_type / reference_id / description: dropping the key only drops the
    # database's at-most-once guarantee (the lock + check in job_refunds.py remains).
    if INDEX in _indexes(LEDGER):
        op.drop_index(INDEX, table_name=LEDGER)
    if 'refund_key' in _columns(LEDGER):
        with op.batch_alter_table(LEDGER) as batch:
            batch.drop_column('refund_key')
