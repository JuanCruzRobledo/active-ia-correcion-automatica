"""CRUD-011: el único de entregas vuelve a ser parcial (deleted_at IS NULL)

Revision ID: e7a3c9d1b502
Revises: 5d12005298a6
Create Date: 2026-08-04

El índice `uq_entrega_rubrica_alumno` cubre hoy TODAS las filas, incluidas las
borradas. Como el borrado de entregas es lógico (`deleted_at`, CRUD-001), una entrega
eliminada sigue ocupando el par (rubrica_id, alumno_nombre): el alta responde 409 y el
alumno no puede volver a entregar. Peor: el listado sí filtra las borradas, así que no
hay forma de ver ni de restaurar lo que lo está bloqueando. El workaround en producción
fue cambiarle una letra al nombre del alumno.

Historia del índice:
  001_initial                  -> parcial, sobre la vieja columna `activo`
  002_remove_activo_entregas   -> total, coherente: ahí el borrado pasó a ser físico
  c1a2b3d4e5f6 (CRUD-001)      -> reintroduce el borrado lógico y NO devuelve el parcial

Esta migración cierra ese hueco. Es segura sobre datos existentes: pasar de un único
total a uno parcial solo AFLOJA la restricción (el conjunto cubierto es un subconjunto),
así que no puede fallar por filas preexistentes — dos filas vivas con el mismo par no
pueden existir, justamente porque el índice total lo impedía.

El downgrade vuelve al índice total. Ojo: si al momento de bajar hay pares repetidos
entre una fila viva y una borrada (exactamente lo que esta migración habilita), el
create_index va a fallar. Es esperable y correcto: bajar exige resolver esos pares a
mano antes.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7a3c9d1b502'
down_revision: Union[str, None] = '5d12005298a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index('uq_entrega_rubrica_alumno', table_name='entregas')
    op.create_index(
        'uq_entrega_rubrica_alumno',
        'entregas',
        ['rubrica_id', 'alumno_nombre'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('uq_entrega_rubrica_alumno', table_name='entregas')
    op.create_index(
        'uq_entrega_rubrica_alumno',
        'entregas',
        ['rubrica_id', 'alumno_nombre'],
        unique=True,
    )
