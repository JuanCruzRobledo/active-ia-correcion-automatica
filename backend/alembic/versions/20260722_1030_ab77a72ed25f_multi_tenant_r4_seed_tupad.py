"""multi-tenant R4: seed universidad TUPaD (data migration)

Revision ID: ab77a72ed25f
Revises: 58da24620545
Create Date: 2026-07-22 10:30:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R4 de 7: inserta la universidad semilla "Tecnicatura Universitaria en
Programación a Distancia" (TUPaD), idempotente por `nombre` (si ya existe, la
reutiliza en vez de duplicarla).

OP-1 (moodle_host de seed, ver design.md "Migration Plan" R4 y Open Questions
#2): el valor se DERIVA del `usuarios.moodle_host` real SOLO si es consistente
(mismo valor no-null en TODOS los usuarios que lo tienen). Si hay valores
distintos o todos son NULL, queda NULL a propósito — NO se inventa una URL.
En ese caso, setearlo a mano post-deploy (paso operativo manual, tasks.md
10.1) es responsabilidad de quien opere el despliegue en producción.
Escrita a mano (requiere lógica condicional, no autogenerable).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ab77a72ed25f'
down_revision: Union[str, None] = '58da24620545'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_TUPAD = "Tecnicatura Universitaria en Programación a Distancia"


def upgrade() -> None:
    bind = op.get_bind()

    existente = bind.execute(
        sa.text("SELECT id FROM universidades WHERE nombre = :nombre"),
        {"nombre": NOMBRE_TUPAD},
    ).first()
    if existente is not None:
        # Idempotente: ya existe (re-ejecución o seed manual previo), no duplicar.
        return

    # OP-1: moodle_host de seed. Derivado de usuarios.moodle_host SOLO si hay un
    # único valor no-null consistente entre todos los usuarios que lo tienen.
    distintos = bind.execute(
        sa.text(
            "SELECT DISTINCT moodle_host FROM usuarios WHERE moodle_host IS NOT NULL"
        )
    ).fetchall()
    moodle_host = distintos[0][0] if len(distintos) == 1 else None

    bind.execute(
        sa.text(
            "INSERT INTO universidades (nombre, moodle_host, activa, created_at, updated_at) "
            "VALUES (:nombre, :moodle_host, true, now(), now())"
        ),
        {"nombre": NOMBRE_TUPAD, "moodle_host": moodle_host},
    )


def downgrade() -> None:
    bind = op.get_bind()
    # Solo borra la fila TUPaD si nada la referencia todavía (revisiones
    # posteriores del backfill son las que la referencian; en downgrade se
    # revierten en orden inverso, así que para cuando llegamos acá ya no
    # debería haber referencias vivas).
    bind.execute(
        sa.text("DELETE FROM universidades WHERE nombre = :nombre"),
        {"nombre": NOMBRE_TUPAD},
    )
