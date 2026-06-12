"""add_job_orchestration_fields

Revision ID: 7c4b5e6e1a90
Revises: b9a30cd2e511
Create Date: 2026-06-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7c4b5e6e1a90'
down_revision: Union[str, Sequence[str], None] = 'b9a30cd2e511'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Add credits to users table
    op.add_column('users', sa.Column('credits', sa.Integer(), server_default='100', nullable=False))

    # 2. Add columns to ai_jobs table
    op.add_column('ai_jobs', sa.Column('user_id', sa.Integer(), nullable=True))
    op.add_column('ai_jobs', sa.Column('brand_id', sa.Integer(), nullable=True))
    op.add_column('ai_jobs', sa.Column('workflow_template_id', sa.Integer(), nullable=True))
    op.add_column(
        'ai_jobs',
        sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}')
    )
    op.add_column(
        'ai_jobs',
        sa.Column('outputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}')
    )
    op.add_column('ai_jobs', sa.Column('callback_url', sa.String(length=1000), nullable=True))
    op.add_column('ai_jobs', sa.Column('error_message', sa.Text(), nullable=True))
    op.add_column(
        'ai_jobs',
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )
    op.add_column(
        'ai_jobs',
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()'))
    )

    # 3. Alter asset_id in ai_jobs to be nullable
    op.alter_column('ai_jobs', 'asset_id', existing_type=sa.Integer(), nullable=True)

    # 4. Modify foreign key constraint for asset_id to SET NULL (first drop cascade constraint)
    # The default naming of foreign key in initial_schema is 'ai_jobs_asset_id_fkey'
    try:
        op.drop_constraint('ai_jobs_asset_id_fkey', 'ai_jobs', type_='foreignkey')
    except Exception:
        # If it doesn't exist, we skip
        pass
    op.create_foreign_key(
        'ai_jobs_asset_id_fkey', 'ai_jobs', 'assets', ['asset_id'], ['id'], ondelete='SET NULL'
    )

    # 5. Add new foreign key constraints
    op.create_foreign_key(
        'fk_ai_jobs_user_id', 'ai_jobs', 'users', ['user_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_ai_jobs_brand_id', 'ai_jobs', 'brands', ['brand_id'], ['id'], ondelete='CASCADE'
    )
    op.create_foreign_key(
        'fk_ai_jobs_workflow_template_id', 'ai_jobs', 'workflow_templates',
        ['workflow_template_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop new foreign keys
    op.drop_constraint('fk_ai_jobs_workflow_template_id', 'ai_jobs', type_='foreignkey')
    op.drop_constraint('fk_ai_jobs_brand_id', 'ai_jobs', type_='foreignkey')
    op.drop_constraint('fk_ai_jobs_user_id', 'ai_jobs', type_='foreignkey')

    # 2. Revert asset_id FK to ondelete=CASCADE
    try:
        op.drop_constraint('ai_jobs_asset_id_fkey', 'ai_jobs', type_='foreignkey')
    except Exception:
        pass
    op.create_foreign_key(
        'ai_jobs_asset_id_fkey', 'ai_jobs', 'assets', ['asset_id'], ['id'], ondelete='CASCADE'
    )

    # 3. Alter asset_id back to NOT NULL
    # NOTE: If we downgrade, we assume existing nulls are handled or it might fail if there are nulls.
    op.alter_column('ai_jobs', 'asset_id', existing_type=sa.Integer(), nullable=False)

    # 4. Drop columns from ai_jobs
    op.drop_column('ai_jobs', 'updated_at')
    op.drop_column('ai_jobs', 'created_at')
    op.drop_column('ai_jobs', 'error_message')
    op.drop_column('ai_jobs', 'callback_url')
    op.drop_column('ai_jobs', 'outputs')
    op.drop_column('ai_jobs', 'inputs')
    op.drop_column('ai_jobs', 'workflow_template_id')
    op.drop_column('ai_jobs', 'brand_id')
    op.drop_column('ai_jobs', 'user_id')

    # 5. Drop credits from users
    op.drop_column('users', 'credits')
