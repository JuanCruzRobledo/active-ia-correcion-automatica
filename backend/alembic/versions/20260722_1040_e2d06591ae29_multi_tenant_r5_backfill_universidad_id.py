"""multi-tenant R5: backfill de universidad_id en cascada (data migration)

Revision ID: e2d06591ae29
Revises: ab77a72ed25f
Create Date: 2026-07-22 10:40:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R5 de 7: backfillea `universidad_id` en las 9 tablas del árbol propagando
desde `materias` (que recibe el id de TUPaD directo) hacia abajo, en el orden
de la cadena de FKs confirmada en design.md (D1):

    materias (directo)
    -> comisiones (via materia_id)
       -> entregas (via comision_id)
          -> correcciones (via entrega_id)
    -> unidades / rubricas / examenes_materia / cierre_cursada_runs /
       avance_snapshots (via materia_id)

Verifica al final que ninguna de las 9 tablas quedó con universidad_id NULL
(red de seguridad antes del NOT NULL de R7). Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e2d06591ae29'
down_revision: Union[str, None] = 'ab77a72ed25f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_TUPAD = "Tecnicatura Universitaria en Programación a Distancia"

# Tablas que propagan universidad_id vía materia_id -> materias.universidad_id.
TABLAS_VIA_MATERIA = [
    'unidades',
    'rubricas',
    'examenes_materia',
    'cierre_cursada_runs',
    'avance_snapshots',
]

TODAS_LAS_TABLAS = [
    'materias', 'comisiones', 'entregas', 'correcciones',
] + TABLAS_VIA_MATERIA


def upgrade() -> None:
    bind = op.get_bind()

    id_tupad = bind.execute(
        sa.text("SELECT id FROM universidades WHERE nombre = :nombre"),
        {"nombre": NOMBRE_TUPAD},
    ).scalar_one()

    bind.execute(
        sa.text("UPDATE materias SET universidad_id = :id WHERE universidad_id IS NULL"),
        {"id": id_tupad},
    )
    bind.execute(
        sa.text(
            "UPDATE comisiones c SET universidad_id = m.universidad_id "
            "FROM materias m WHERE c.materia_id = m.id AND c.universidad_id IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE entregas e SET universidad_id = c.universidad_id "
            "FROM comisiones c WHERE e.comision_id = c.id AND e.universidad_id IS NULL"
        )
    )
    bind.execute(
        sa.text(
            "UPDATE correcciones co SET universidad_id = e.universidad_id "
            "FROM entregas e WHERE co.entrega_id = e.id AND co.universidad_id IS NULL"
        )
    )
    for tabla in TABLAS_VIA_MATERIA:
        bind.execute(
            sa.text(
                f"UPDATE {tabla} t SET universidad_id = m.universidad_id "
                f"FROM materias m WHERE t.materia_id = m.id AND t.universidad_id IS NULL"
            )
        )

    # Red de seguridad: ninguna de las 9 tablas debe quedar con NULL antes de R7.
    for tabla in TODAS_LAS_TABLAS:
        pendientes = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {tabla} WHERE universidad_id IS NULL")
        ).scalar_one()
        if pendientes:
            raise RuntimeError(
                f"multi-tenant R5: {tabla} quedó con {pendientes} fila(s) "
                "universidad_id IS NULL tras el backfill. Abortando antes de R7."
            )


def downgrade() -> None:
    bind = op.get_bind()
    for tabla in reversed(TODAS_LAS_TABLAS):
        bind.execute(sa.text(f"UPDATE {tabla} SET universidad_id = NULL"))
