"""add notifications table and user notification preferences

Revision ID: notifications_001
Revises: user_low_credit_warning_001
Create Date: 2026-07-03

"""
from alembic import op
import sqlalchemy as sa

revision = 'notifications_001'
down_revision = 'user_low_credit_warning_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add notification preferences to users table
    op.add_column('users', sa.Column('notify_on_job_complete', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('notify_on_training_complete', sa.Boolean(), nullable=False, server_default='true'))

    # Create notifications table
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('type', sa.String(100), nullable=False, index=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('notifications')
    op.drop_column('users', 'notify_on_job_complete')
    op.drop_column('users', 'notify_on_training_complete')
