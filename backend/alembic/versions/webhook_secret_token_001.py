"""add secret_token to webhook_subscriptions

Revision ID: webhook_secret_token_001
Revises: character_version_mlflow_001
Create Date: 2026-07-02

"""
from alembic import op
import sqlalchemy as sa
import secrets

revision = 'webhook_secret_token_001'
down_revision = 'character_version_mlflow_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('webhook_subscriptions', sa.Column('secret_token', sa.String(200), nullable=True))

    # Generate fallback secrets for existing records
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT id FROM webhook_subscriptions WHERE secret_token IS NULL"))
    rows = result.fetchall()
    for row in rows:
        token = f"ml_sec_{secrets.token_hex(32)}"
        conn.execute(
            sa.text("UPDATE webhook_subscriptions SET secret_token = :token WHERE id = :id"),
            {"token": token, "id": row[0]}
        )


def downgrade() -> None:
    op.drop_column('webhook_subscriptions', 'secret_token')
