"""PERF-015: add index on entregas.updated_at

Revision ID: b9c4d1e5f3a6
Revises: a8f3c9d1e2b4
Create Date: 2026-07-18 16:00:00.000000

Hallazgo PERF-015 (docs/auditoria/03-optimizacion.md): el polling de novedades
consulta `MAX(updated_at) + COUNT(id)` sobre `entregas` cada ~45s por cliente
(EntregaRepository.version, entrega_repository.py:38-44). La columna `updated_at`
proviene del TimestampMixin (base.py:58-62), que NO la indexa → el agregado hace
un scan completo de la tabla.

El índice se declara SCOPED en Entrega.__table_args__ (no en el mixin, que está
COMPARTIDO por muchas tablas y las indexaría todas), siguiendo el mismo patrón que
ix_entregas_created_at (PERF-016).

Migración ADITIVA y no destructiva: solo crea un índice. Escrita a mano (sin DB
disponible para autogenerate). Nombre explícito para que create/drop sean
simétricos con el downgrade.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b9c4d1e5f3a6'
down_revision: Union[str, None] = 'a8f3c9d1e2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_entregas_updated_at',
        'entregas',
        ['updated_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_entregas_updated_at', table_name='entregas')
