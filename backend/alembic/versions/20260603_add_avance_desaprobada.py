"""add actividad_actual_desaprobada to avance_alumnos

Revision ID: 013_avance_desaprobada
Revises: a1fc51f49e64
Create Date: 2026-06-03

Marca si la actividad de mayor unidad alcanzada por el alumno fue completada pero
REPROBADA (state 3 de Moodle). El alumno avanzó (cuenta para la unidad) pero se
muestra como "completo y desaprobado". Ref: PLAN_DASHBOARD_GESTORES.md.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013_avance_desaprobada"
down_revision: Union[str, None] = "a1fc51f49e64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "avance_alumnos",
        sa.Column(
            "actividad_actual_desaprobada",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("avance_alumnos", "actividad_actual_desaprobada")
