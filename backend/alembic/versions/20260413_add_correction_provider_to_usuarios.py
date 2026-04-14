"""Add correction_provider column to usuarios

Revision ID: 009_add_correction_provider
Revises: 008_add_penalizacion_fields
Create Date: 2026-04-13

Stores the user's preferred correction provider ('gemini' or 'claude_cli').
Defaults to 'gemini' so existing users keep their current behavior.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '009_add_correction_provider'
down_revision: Union[str, None] = '008_add_penalizacion_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'usuarios' AND column_name = 'correction_provider'"
        )
    )
    if not result.fetchone():
        op.add_column(
            'usuarios',
            sa.Column(
                'correction_provider',
                sa.String(50),
                nullable=False,
                server_default='gemini',
            ),
        )


def downgrade() -> None:
    op.drop_column('usuarios', 'correction_provider')
