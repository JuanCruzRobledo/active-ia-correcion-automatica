"""rubrica: agregar tipo TPI (Trabajo Práctico Integrador)

Revision ID: e5f6a7b8c9d0
Revises: af527d2fc7a0
Create Date: 2026-06-18 12:00:00.000000

Agrega el valor TPI al enum tiporubricaenum para soportar rúbricas de
Trabajo Práctico Integrador.
ALTER TYPE ... ADD VALUE no puede correr dentro de una transaccion -> autocommit_block.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'af527d2fc7a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE tiporubricaenum ADD VALUE IF NOT EXISTS 'TPI'")


def downgrade() -> None:
    # Postgres no soporta quitar valores de un enum; downgrade no-op.
    pass
