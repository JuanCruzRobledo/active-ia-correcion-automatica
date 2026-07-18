"""add schema_version to rubricas

Revision ID: 6ea15851ac21
Revises: a7b8c9d0e1f2
Create Date: 2026-07-18 14:54:45.622078

Change `peso-por-subcriterio` (openspec/changes/peso-por-subcriterio): versiona
la estructura de `criterios_json` con una columna `schema_version` en
`rubricas`. v1 = comportamiento actual (subcriterios sin peso propio, reparto
implícito). v2 = subcriterios con peso propio que deben sumar exactamente el
peso del criterio contenedor.

`server_default='1'` asegura que las rúbricas existentes queden en v1 sin
backfill manual — no requiere UPDATE de filas.

NOTA: el autogenerate de Alembic detectó además una serie de diffs de drift
preexistentes y no relacionados con este cambio (comentarios de columnas en
`avance_alumnos`/`cierre_cursada_*`/`materias`, server_default de
`moodle_sync.intento`/`created_at`/`updated_at`, y el `ondelete` del FK
`moodle_sync.enviado_por_id`). Se excluyen deliberadamente de esta migración
para mantenerla enfocada en el cambio de `peso-por-subcriterio`; quedan como
deuda de otro change si hace falta sincronizarlos.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6ea15851ac21'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'rubricas',
        sa.Column(
            'schema_version',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
            comment=(
                "Versión del schema de criterios_json (1 = sin peso por "
                "subcriterio, 2 = con peso por subcriterio)"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column('rubricas', 'schema_version')
