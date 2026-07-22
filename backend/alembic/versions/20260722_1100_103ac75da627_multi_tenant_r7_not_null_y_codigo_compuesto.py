"""multi-tenant R7: universidad_id NOT NULL + unique compuesto de materias.codigo

Revision ID: 103ac75da627
Revises: ea7c83500aac
Create Date: 2026-07-22 11:00:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R7 de 7 (structural, post-backfill): endurece `universidad_id` a NOT NULL en
las 9 tablas del árbol (falla en seco si R5/R6 dejaron algún NULL — es la red
de seguridad intencional, ver design.md "Migration Plan" R7). Reemplaza el
unique global de `materias.codigo` por `UniqueConstraint(universidad_id,
codigo)` (D5 del design.md).

El nombre real del unique viejo de `materias.codigo` se confirmó con
`\\d materias` (psql) contra la base real de Docker (no contra lo que sugería, por sí
sola, la migración inicial): en la base viva EXISTE ÚNICAMENTE el índice
único `ix_materias_codigo` — NO hay una `uq_materias_codigo` como constraint
de tabla separada (pese a que `20260126_1720_001_initial_initial_schema.py`
la declara en el `create_table`; aparentemente nunca quedó materializada como
tal, o fue reemplazada en algún punto). Por eso R7 dropea solo el índice.
Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '103ac75da627'
down_revision: Union[str, None] = 'ea7c83500aac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLAS_ARBOL = [
    'materias',
    'comisiones',
    'entregas',
    'correcciones',
    'unidades',
    'rubricas',
    'examenes_materia',
    'cierre_cursada_runs',
    'avance_snapshots',
]


def upgrade() -> None:
    for tabla in TABLAS_ARBOL:
        op.alter_column(
            tabla, 'universidad_id', existing_type=sa.Integer(), nullable=False,
        )

    # Reemplazo del unique global de materias.codigo por el compuesto
    # (universidad_id, codigo). En la base real (verificado con \d materias) el
    # unique viejo vive SOLO en el índice único ix_materias_codigo — no hay una
    # uq_materias_codigo como constraint de tabla separada.
    op.drop_index('ix_materias_codigo', table_name='materias')
    op.create_unique_constraint(
        'uq_materias_universidad_id_codigo', 'materias', ['universidad_id', 'codigo'],
    )


def downgrade() -> None:
    op.drop_constraint(
        'uq_materias_universidad_id_codigo', 'materias', type_='unique',
    )
    op.create_index('ix_materias_codigo', 'materias', ['codigo'], unique=True)

    for tabla in reversed(TABLAS_ARBOL):
        op.alter_column(
            tabla, 'universidad_id', existing_type=sa.Integer(), nullable=True,
        )
