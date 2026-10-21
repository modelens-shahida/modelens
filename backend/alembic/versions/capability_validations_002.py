"""capability validations: catch-up backfill before customer routes read PROMOTED records

From this revision on, customer option routes and production dispatch only
offer what is PROMOTED in ``capability_validations`` (Character Runtime PR 3).
``capability_validations_001`` backfilled everything live when it ran; an
option made live in the definition tables after that (appearance option or
capability pack in PRODUCTION, a pose offered for a product type, a preset in
PRODUCTION) would disappear for customers. This revision runs the same
backfill again so it gets a PROMOTED record too.

It is the backfill of ``capability_validations_001`` itself (loaded from that
file, which is frozen): insert-only, never updates or deletes a row, skips
anything that already has a record (in any status, so a capability an admin
retired stays retired), and is safe to run again. No schema change; downgrade
does nothing (the records are indistinguishable from 001's and are kept).

Revision ID: capability_validations_002
Revises: capability_validations_001
Create Date: 2026-10-21
"""
import importlib.util
import os

from alembic import op

revision = 'capability_validations_002'
down_revision = 'capability_validations_001'
branch_labels = None
depends_on = None


def _revision_001():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'capability_validations_001.py')
    spec = importlib.util.spec_from_file_location('capability_validations_001_frozen', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def upgrade():
    inserted = _revision_001().backfill(op.get_bind())
    print(f'[migration] capability_validations: catch-up backfilled {inserted} PROMOTED records')


def downgrade():
    pass
