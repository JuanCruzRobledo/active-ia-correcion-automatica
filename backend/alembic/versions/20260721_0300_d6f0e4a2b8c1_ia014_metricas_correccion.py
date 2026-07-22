"""IA-014: columnas de consumo (tokens/modelo/proveedor) en correcciones

Revision ID: d6f0e4a2b8c1
Revises: c5f9a3b7d1e0
Create Date: 2026-07-21 03:00:00.000000

Hallazgo IA-014: el consumo de tokens se guardaba SOLO en raw_response (JSONB
deferred), sin agregación ni visibilidad de costos. Se agregan columnas queryables
a correcciones para poder agregar el gasto sin parsear el crudo.

Migración ADITIVA (4 columnas nullable). Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd6f0e4a2b8c1'
down_revision: Union[str, None] = 'c5f9a3b7d1e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("correcciones", sa.Column("tokens_entrada", sa.Integer(), nullable=True))
    op.add_column("correcciones", sa.Column("tokens_salida", sa.Integer(), nullable=True))
    op.add_column("correcciones", sa.Column("ia_modelo", sa.String(length=100), nullable=True))
    op.add_column("correcciones", sa.Column("ia_proveedor", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("correcciones", "ia_proveedor")
    op.drop_column("correcciones", "ia_modelo")
    op.drop_column("correcciones", "tokens_salida")
    op.drop_column("correcciones", "tokens_entrada")
