"""examen tipo_actividad (assign vs quiz)

Revision ID: f5a6b7c8d9e0
Revises: e4f5a6b7c8d9
Create Date: 2026-07-06 10:00:00.000000

Bug 1 de `.kiro/specs/cierre-cursada-quiz-recuperables-fix`: `ExamenMateria`
no distinguía si la actividad de Moodle es Tarea (`assign`) o Cuestionario
(`quiz`), por lo que el link/recurso y la fuente de notas asumían siempre
`assign`. Se agrega la columna `tipo_actividad` (enum nativo
`tipoactividadmoodleenum` con valores `assign`/`quiz`).

Los registros existentes quedan en `assign` (NOT NULL DEFAULT 'assign'), que
reproduce exactamente el comportamiento histórico (cumple el requisito 2.2).

Escrita a mano (mismo estilo que
`20260610_1600_b2c3d4e5f6a7_examenes_materia.py`: creación explícita del enum
nativo con `checkfirst`, `create_type=False` en la columna, DROP TYPE explícito
en el downgrade).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f5a6b7c8d9e0'
down_revision: Union[str, None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # 1. Crear el tipo enum nativo (idempotente con checkfirst).
    tipo_actividad_enum = postgresql.ENUM(
        'assign', 'quiz', name='tipoactividadmoodleenum',
    )
    tipo_actividad_enum.create(bind, checkfirst=True)

    # 2. Agregar la columna NOT NULL con default 'assign' -> los registros
    #    existentes quedan en 'assign' (comportamiento histórico, requisito 2.2).
    op.add_column(
        'examenes_materia',
        sa.Column(
            'tipo_actividad',
            postgresql.ENUM(name='tipoactividadmoodleenum', create_type=False),
            nullable=False,
            server_default='assign',
            comment='Actividad de Moodle: assign (Tarea) | quiz (Cuestionario)',
        ),
    )


def downgrade() -> None:
    op.drop_column('examenes_materia', 'tipo_actividad')

    bind = op.get_bind()
    sa.Enum(name='tipoactividadmoodleenum').drop(bind, checkfirst=True)
