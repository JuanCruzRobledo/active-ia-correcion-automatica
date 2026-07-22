"""PERF-016: add indexes on comision_tutor.tutor_id and entregas.created_at

Revision ID: a8f3c9d1e2b4
Revises: 6ea15851ac21
Create Date: 2026-07-18 15:00:00.000000

Hallazgo PERF-016 (docs/auditoria/03-optimizacion.md): faltan índices en
columnas usadas para filtrar/ordenar frecuentemente.

- `comision_tutor.tutor_id`: el unique `(comision_id, tutor_id)` solo sirve como
  prefijo para buscar por comisión, no por tutor solo. Las queries
  `get_subidas_ids_by_tutor`, `contar_estados_by_tutor` y `contar_errores_by_tutor`
  (entrega_repository.py:333-377) filtran/joinean por `ComisionTutor.tutor_id`
  aislado y hoy hacen seq scan.
- `entregas.created_at`: el listado de entregas ordena por `created_at DESC`
  (entrega_repository.py:152) sin índice → seq scan + sort. El TimestampMixin
  (base.py:54-62) no indexa la columna.

Migración ADITIVA y no destructiva: solo crea índices. Escrita a mano (sin DB
disponible para autogenerate). Nombres explícitos para que create/drop sean
simétricos con el downgrade.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a8f3c9d1e2b4'
down_revision: Union[str, None] = '6ea15851ac21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_comision_tutor_tutor_id',
        'comision_tutor',
        ['tutor_id'],
        unique=False,
    )
    op.create_index(
        'ix_entregas_created_at',
        'entregas',
        ['created_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_entregas_created_at', table_name='entregas')
    op.drop_index('ix_comision_tutor_tutor_id', table_name='comision_tutor')
