"""cierre ABANDONO (estado + total_abandono)

Revision ID: a7b8c9d0e1f2
Revises: f5a6b7c8d9e0
Create Date: 2026-07-06 11:00:00.000000

Bug 5 de `.kiro/specs/cierre-cursada-quiz-recuperables-fix`: hoy un alumno que
no rindió ningún examen ni el global (todo en `N/E`) se clasifica como RECURSA.
El comportamiento correcto es clasificarlo con un nuevo estado ABANDONO, contado
aparte de RECURSA.

Esta migración:
  1. Agrega el valor `ABANDONO` al enum nativo `estadocierreenum`.
  2. Agrega la columna `total_abandono` (NOT NULL DEFAULT 0) a
     `cierre_cursada_runs` para persistir el conteo del nuevo estado.

CAVEAT TRANSACCIONAL (PostgreSQL): `ALTER TYPE ... ADD VALUE` no puede ejecutarse
dentro de un bloque transaccional en algunas versiones de PostgreSQL (pre-12, y
en general cuando el nuevo valor se usa en la misma transacción). Alembic corre
cada migración dentro de una transacción, así que primero se cierra la
transacción abierta con `op.execute("COMMIT")` y recién después se ejecuta el
`ALTER TYPE ... ADD VALUE IF NOT EXISTS`. El `IF NOT EXISTS` la hace idempotente.

DOWNGRADE: se elimina la columna `total_abandono`. NO se elimina el valor
`ABANDONO` del enum: PostgreSQL no soporta quitar valores de un enum
(`ALTER TYPE ... DROP VALUE` no existe), y dejar el valor en su lugar es seguro
(no rompe datos ni el esquema).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f5a6b7c8d9e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar el valor ABANDONO al enum nativo `estadocierreenum`.
    #    ADD VALUE no corre dentro de una transacción en algunas versiones de
    #    PostgreSQL: cerramos la transacción de Alembic con COMMIT y luego lo
    #    ejecutamos en autocommit. IF NOT EXISTS lo hace idempotente.
    op.execute("COMMIT")
    op.execute("ALTER TYPE estadocierreenum ADD VALUE IF NOT EXISTS 'ABANDONO'")

    # 2. Agregar la columna de conteo `total_abandono` (NOT NULL DEFAULT 0).
    op.add_column(
        'cierre_cursada_runs',
        sa.Column(
            'total_abandono',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment="Conteo de alumnos ABANDONO (no rindieron ningún examen ni el global)",
        ),
    )


def downgrade() -> None:
    op.drop_column('cierre_cursada_runs', 'total_abandono')
    # El valor 'ABANDONO' del enum `estadocierreenum` se deja en su lugar:
    # PostgreSQL no soporta quitar valores de un enum y dejarlo es seguro.
