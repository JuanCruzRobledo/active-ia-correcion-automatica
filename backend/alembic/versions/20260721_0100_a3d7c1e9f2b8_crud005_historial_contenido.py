"""CRUD-005: contenido real en entregas_historial

Revision ID: a3d7c1e9f2b8
Revises: 5782f7f9bd0d
Create Date: 2026-07-21 01:00:00.000000

Hallazgo CRUD-005: al sobrescribir una entrega, EntregaHistorial guardaba solo
contenido_preview (500 chars); el contenido_consolidado (el trabajo real del
alumno) se perdía al pisarse. Se agregan las columnas para preservarlo.

Migración ADITIVA (dos columnas nullable). Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a3d7c1e9f2b8'
down_revision: Union[str, None] = '5782f7f9bd0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("entregas_historial", sa.Column("contenido_consolidado", sa.Text(), nullable=True))
    op.add_column("entregas_historial", sa.Column("pdf_contenido_b64", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("entregas_historial", "pdf_contenido_b64")
    op.drop_column("entregas_historial", "contenido_consolidado")
