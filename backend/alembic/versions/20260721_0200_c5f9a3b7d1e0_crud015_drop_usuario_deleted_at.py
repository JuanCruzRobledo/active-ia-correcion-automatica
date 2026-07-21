"""CRUD-015: drop usuarios.deleted_at (campo muerto)

Revision ID: c5f9a3b7d1e0
Revises: b4e8d2c0a1f9
Create Date: 2026-07-21 02:00:00.000000

Hallazgo CRUD-015: Usuario heredaba SoftDeleteMixin (deleted_at) pero su soft
delete real es `activo`; ningún código setea Usuario.deleted_at. El campo existía
siempre NULL y confundía. Se elimina de la tabla usuarios (TutorNexo, que sí usa
el mixin, no se toca).

Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c5f9a3b7d1e0'
down_revision: Union[str, None] = 'b4e8d2c0a1f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("usuarios", "deleted_at")


def downgrade() -> None:
    op.add_column("usuarios", sa.Column("deleted_at", sa.DateTime(), nullable=True))
