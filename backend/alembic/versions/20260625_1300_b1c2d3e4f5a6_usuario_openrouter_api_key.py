"""usuario openrouter_api_key_encrypted + openrouter_api_key_valid

Revision ID: b1c2d3e4f5a6
Revises: fac93e85383e
Create Date: 2026-06-25 13:00:00.000000

Agrega la API key de OpenRouter por separado de la de Gemini Studio. El modo de
corrección elegido vive en correction_provider (ya existente, default 'gemini').
Escrita a mano para no arrastrar el drift de autogenerate en otras tablas.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'fac93e85383e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'usuarios',
        sa.Column('openrouter_api_key_encrypted', sa.Text(), nullable=True),
    )
    op.add_column(
        'usuarios',
        sa.Column(
            'openrouter_api_key_valid',
            sa.Boolean(),
            server_default=sa.text('false'),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'openrouter_api_key_valid')
    op.drop_column('usuarios', 'openrouter_api_key_encrypted')
