"""CRUD-004: drop archivo_ruta (ruta fantasma)

Revision ID: b4e8d2c0a1f9
Revises: a3d7c1e9f2b8
Create Date: 2026-07-21 01:30:00.000000

Hallazgo CRUD-004: archivo_ruta se fabricaba como `/uploads/entregas/{hash}_{name}`
pero el archivo NUNCA se escribía a disco (no hay file storage). Era un dato
mentiroso en la DB y en la API, y el os.remove(archivo_ruta) de las cascadas de
hard delete era código muerto. Se elimina la columna de entregas y entregas_historial.

Escrita a mano. Downgrade la re-agrega como nullable (no tiene sentido reconstruir
el valor fantasma).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b4e8d2c0a1f9'
down_revision: Union[str, None] = 'a3d7c1e9f2b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("entregas", "archivo_ruta")
    op.drop_column("entregas_historial", "archivo_ruta")


def downgrade() -> None:
    op.add_column("entregas", sa.Column("archivo_ruta", sa.String(length=500), nullable=True))
    op.add_column("entregas_historial", sa.Column("archivo_ruta", sa.String(length=500), nullable=True))
