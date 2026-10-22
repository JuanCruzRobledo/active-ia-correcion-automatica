"""Persist the user's OpenRouter model preference.

Revision ID: f8b4d2e6c901
Revises: e7a3c9d1b502
"""
import sqlalchemy as sa
from alembic import op

revision = "f8b4d2e6c901"
down_revision = "e7a3c9d1b502"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("openrouter_model", sa.String(200),
        nullable=False, server_default="google/gemini-3.8-flash"))


def downgrade() -> None:
    op.drop_column("usuarios", "openrouter_model")
