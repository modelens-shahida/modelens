"""stripe customer id on users, unique Stripe reference on the credit ledger

* ``users.stripe_customer_id``: nullable, unique index
  ``ix_users_stripe_customer_id`` (NULLs allowed, so users who never checked
  out are unaffected). The billing portal reads it instead of looking the
  customer up by email.
* ``credit_transactions.stripe_reference``: nullable, unique index
  ``ix_credit_transactions_stripe_reference``. Holds the Stripe checkout
  session / invoice id that granted the credits, so the database itself stops
  a second grant for the same id. NULL for every non-Stripe row.
* Backfill: Stripe grants were recorded with ``reference_type =
  'purchase_invoice'`` and the Stripe id in ``reference_id`` (mock purchases
  use the same type with ``reference_id`` NULL and are not touched). Those ids
  are copied into ``stripe_reference``. If two rows would share an id, the
  upgrade stops before changing anything and lists them; nothing is deleted.

Columns and indexes are only added when missing: safe to run twice.

Revision ID: stripe_customer_ledger_001
Revises: presets_registry_001
Create Date: 2026-10-14
"""
from alembic import op
import sqlalchemy as sa

revision = 'stripe_customer_ledger_001'
down_revision = 'presets_registry_001'
branch_labels = None
depends_on = None

USERS, LEDGER = 'users', 'credit_transactions'
USERS_INDEX = 'ix_users_stripe_customer_id'
LEDGER_INDEX = 'ix_credit_transactions_stripe_reference'


class DuplicateStripeReferences(RuntimeError):
    pass


def _columns(table):
    return {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table):
    return {i['name'] for i in sa.inspect(op.get_bind()).get_indexes(table)}


def _duplicate_references(bind):
    """Stripe ids that would appear on more than one row once backfilled."""
    backfilled = "CASE WHEN reference_type = 'purchase_invoice' THEN reference_id END"
    if 'stripe_reference' in _columns(LEDGER):
        backfilled = f"COALESCE(stripe_reference, {backfilled})"
    return bind.execute(sa.text(
        f"SELECT ref, COUNT(*) AS n FROM (SELECT {backfilled} AS ref FROM credit_transactions) AS refs "
        "WHERE ref IS NOT NULL GROUP BY ref HAVING COUNT(*) > 1 ORDER BY ref"
    )).all()


def upgrade():
    bind = op.get_bind()

    # Checked before any schema change, so a stopped upgrade leaves nothing behind
    # (SQLite does not roll back DDL the way Postgres does).
    duplicates = _duplicate_references(bind)
    if duplicates:
        listed = ', '.join(f'{ref} ({n} rows)' for ref, n in duplicates)
        raise DuplicateStripeReferences(
            f'credit_transactions has Stripe references that granted credits more than once: {listed}. '
            'The upgrade was stopped before changing anything and nothing was deleted. '
            'Review these rows (and any extra credits they granted) with the team, then re-run the upgrade.'
        )

    if 'stripe_customer_id' not in _columns(USERS):
        op.add_column(USERS, sa.Column('stripe_customer_id', sa.String(255), nullable=True))
    if USERS_INDEX not in _indexes(USERS):
        op.create_index(USERS_INDEX, USERS, ['stripe_customer_id'], unique=True)

    if 'stripe_reference' not in _columns(LEDGER):
        op.add_column(LEDGER, sa.Column('stripe_reference', sa.String(255), nullable=True))
    bind.execute(sa.text(
        "UPDATE credit_transactions SET stripe_reference = reference_id "
        "WHERE stripe_reference IS NULL AND reference_type = 'purchase_invoice' AND reference_id IS NOT NULL"
    ))
    if LEDGER_INDEX not in _indexes(LEDGER):
        op.create_index(LEDGER_INDEX, LEDGER, ['stripe_reference'], unique=True)


def downgrade():
    # reference_id still holds every Stripe id, so dropping stripe_reference loses nothing.
    if LEDGER_INDEX in _indexes(LEDGER):
        op.drop_index(LEDGER_INDEX, table_name=LEDGER)
    if 'stripe_reference' in _columns(LEDGER):
        with op.batch_alter_table(LEDGER) as batch:
            batch.drop_column('stripe_reference')

    if USERS_INDEX in _indexes(USERS):
        op.drop_index(USERS_INDEX, table_name=USERS)
    if 'stripe_customer_id' in _columns(USERS):
        with op.batch_alter_table(USERS) as batch:
            batch.drop_column('stripe_customer_id')
