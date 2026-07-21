"""CRUD-001: soft delete de entregas (deleted_at) + tipos de auditoria de borrado

Revision ID: c1a2b3d4e5f6
Revises: b9c4d1e5f3a6
Create Date: 2026-07-20 12:00:00.000000

Hallazgo CRUD-001 (docs/auditoria/02-cruds.md): Entrega se borraba FISICAMENTE
siempre (db.delete incondicional), sin gate ni registro de auditoria, violando la
regla dura del proyecto (soft delete obligatorio). Se agrega deleted_at via el
SoftDeleteMixin ya existente (base.py:65) para baja logica con marca temporal.

Dos cambios:
1. add_column entregas.deleted_at (DateTime, nullable): las filas existentes
   quedan en NULL = no borradas. El default None del mixin es del lado Python.
2. ALTER TYPE tipoactividadenum ADD VALUE: los dos primeros tipos de auditoria de
   BORRADO del sistema. El enum es nativo de Postgres (Actividad.tipo usa
   SQLEnum(create_type=False)), asi que autogenerate NO detecta valores nuevos;
   por eso la migracion se escribe a mano. IF NOT EXISTS = idempotente; PG15
   permite ADD VALUE dentro de transaccion (no se usa el valor en la misma tx).

Migracion ADITIVA y no destructiva. El downgrade solo dropea la columna: Postgres
no soporta DROP VALUE en un ENUM, asi que los dos valores agregados quedan
huerfanos (inocuos: nadie los referencia tras el drop). Es el patron estandar de
Alembic para reversion de enum-add.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c1a2b3d4e5f6'
down_revision: Union[str, None] = 'b9c4d1e5f3a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entregas", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.execute("ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'ENTREGA_ELIMINADA'")
    op.execute("ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'ENTREGA_RESTAURADA'")


def downgrade() -> None:
    op.drop_column("entregas", "deleted_at")
    # Postgres no soporta DROP VALUE: ENTREGA_ELIMINADA / ENTREGA_RESTAURADA quedan
    # en el ENUM. Inocuo tras el drop_column; patron estandar de Alembic.
