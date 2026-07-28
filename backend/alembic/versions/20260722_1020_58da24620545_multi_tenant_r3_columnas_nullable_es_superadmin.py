"""multi-tenant R3: universidad_id nullable en 9 tablas + usuarios.es_superadmin

Revision ID: 58da24620545
Revises: b7cd41aa7f5e
Create Date: 2026-07-22 10:20:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R3 de 7: agrega `universidad_id` (FK -> universidades.id, NULLABLE por ahora,
se endurece a NOT NULL en R7 tras el backfill) a las 9 tablas del árbol de
Materia, y `usuarios.es_superadmin` (NOT NULL, default false). Puramente
estructural y aditiva — no rompe nada existente. Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '58da24620545'
down_revision: Union[str, None] = 'b7cd41aa7f5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Las 9 tablas del árbol de Materia (D1/D2 del design.md).
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
        op.add_column(
            tabla,
            sa.Column('universidad_id', sa.Integer(), nullable=True),
        )
        op.create_index(
            op.f(f'ix_{tabla}_universidad_id'), tabla, ['universidad_id'], unique=False,
        )
        op.create_foreign_key(
            op.f(f'fk_{tabla}_universidad_id_universidades'),
            tabla, 'universidades', ['universidad_id'], ['id'],
        )

    op.add_column(
        'usuarios',
        sa.Column(
            'es_superadmin', sa.Boolean(), nullable=False, server_default=sa.text('false'),
        ),
    )


def downgrade() -> None:
    op.drop_column('usuarios', 'es_superadmin')

    for tabla in reversed(TABLAS_ARBOL):
        op.drop_constraint(
            op.f(f'fk_{tabla}_universidad_id_universidades'), tabla, type_='foreignkey',
        )
        op.drop_index(op.f(f'ix_{tabla}_universidad_id'), table_name=tabla)
        op.drop_column(tabla, 'universidad_id')
