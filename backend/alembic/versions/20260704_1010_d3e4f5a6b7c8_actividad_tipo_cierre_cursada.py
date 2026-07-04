"""actividad: tipo CIERRE_CURSADA_GENERADO

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-07-04 10:10:00.000000

Agrega el valor CIERRE_CURSADA_GENERADO al enum tipoactividadenum, para
auditar la generación de un cierre de cursada. ALTER TYPE ... ADD VALUE no
puede correr dentro de una transacción -> autocommit_block (mismo patrón que
20260611_0100_d4e5f6a7b8c9_actividad_tipos_nuevos.py).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'CIERRE_CURSADA_GENERADO'"
        )


def downgrade() -> None:
    # Postgres no soporta quitar valores de un enum; downgrade no-op.
    pass
