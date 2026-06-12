"""umbrales riesgo configurables por materia

Agrega los umbrales de riesgo configurables por materia (riesgo_medio_desde /
riesgo_alto_desde) y su copia CONGELADA en cada snapshot. Defaults 1 y 2 =
comportamiento histórico (1 unidad atrás = riesgo medio, 2+ = riesgo alto).

Revision ID: 870c3f7ebcc9
Revises: d4e5f6a7b8c9
Create Date: 2026-06-12 15:01:09.190305

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '870c3f7ebcc9'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Umbrales configurables en la materia (NOT NULL con default = regla histórica,
    # así las filas existentes quedan en 1/2 sin cambiar de comportamiento).
    op.add_column(
        'materias',
        sa.Column(
            'riesgo_medio_desde', sa.Integer(), server_default='1', nullable=False,
            comment='Atraso (delta) a partir del cual el alumno entra en RIESGO_MEDIO',
        ),
    )
    op.add_column(
        'materias',
        sa.Column(
            'riesgo_alto_desde', sa.Integer(), server_default='2', nullable=False,
            comment='Atraso (delta) a partir del cual el alumno entra en RIESGO_ALTO (> medio)',
        ),
    )
    # Copia CONGELADA en el snapshot (nullable: los snapshots viejos se leen con 1/2).
    op.add_column(
        'avance_snapshots',
        sa.Column(
            'riesgo_medio_desde', sa.Integer(), nullable=True,
            comment='materia.riesgo_medio_desde CONGELADO al momento del snapshot',
        ),
    )
    op.add_column(
        'avance_snapshots',
        sa.Column(
            'riesgo_alto_desde', sa.Integer(), nullable=True,
            comment='materia.riesgo_alto_desde CONGELADO al momento del snapshot',
        ),
    )


def downgrade() -> None:
    op.drop_column('avance_snapshots', 'riesgo_alto_desde')
    op.drop_column('avance_snapshots', 'riesgo_medio_desde')
    op.drop_column('materias', 'riesgo_alto_desde')
    op.drop_column('materias', 'riesgo_medio_desde')
