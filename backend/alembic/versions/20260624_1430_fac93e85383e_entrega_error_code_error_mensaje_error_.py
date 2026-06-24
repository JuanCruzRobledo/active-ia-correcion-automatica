"""entrega error_code error_mensaje error_at (item 1)

Revision ID: fac93e85383e
Revises: e5f6a7b8c9d0
Create Date: 2026-06-24 14:30:48.906981

Solo agrega las 3 columnas de detalle de error en `entregas` (item #1). El autogenerate
detectó además drift de comentarios/server_defaults/FK en otras tablas — se omiten a
propósito: no son parte de este cambio.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fac93e85383e'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('entregas', sa.Column('error_code', sa.String(length=50), nullable=True))
    op.add_column('entregas', sa.Column('error_mensaje', sa.Text(), nullable=True))
    op.add_column('entregas', sa.Column('error_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('entregas', 'error_at')
    op.drop_column('entregas', 'error_mensaje')
    op.drop_column('entregas', 'error_code')
