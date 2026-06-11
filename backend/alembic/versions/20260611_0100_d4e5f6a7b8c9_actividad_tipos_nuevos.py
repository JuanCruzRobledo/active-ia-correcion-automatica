"""actividad: tipos nuevos para funciones nuevas

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-11 01:00:00.000000

Agrega valores al enum tipoactividadenum para registrar acciones manuales de las
funciones nuevas (cohorte, tutor nexo, examen, snapshot manual, notificaciones).
ALTER TYPE ... ADD VALUE no puede correr dentro de una transaccion -> autocommit_block.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NUEVOS = [
    "COHORTE_CREADA",
    "TUTOR_NEXO_CREADO",
    "EXAMEN_CREADO",
    "SNAPSHOT_GENERADO",
    "NOTIFICACIONES_ENVIADAS",
]


def upgrade() -> None:
    with op.get_context().autocommit_block():
        for valor in _NUEVOS:
            op.execute(
                f"ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS '{valor}'"
            )


def downgrade() -> None:
    # Postgres no soporta quitar valores de un enum; downgrade no-op.
    pass
