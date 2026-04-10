"""Add penalization and failing condition fields to correcciones

Revision ID: 008_add_penalizacion_fields
Revises: 007_add_archivado_to_entregas
Create Date: 2026-04-10

Adds columns to correcciones to persist:
- nota_antes_penalizaciones: merit score before penalties/CD
- condicion_desaprobacion_aplicada: ID of applied failing condition
- penalizaciones_aplicadas: array of applied penalty IDs
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '008_add_penalizacion_fields'
down_revision: Union[str, None] = '007_add_archivado_to_entregas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'correcciones',
        sa.Column(
            'nota_antes_penalizaciones',
            sa.Numeric(precision=5, scale=2),
            nullable=True,
        ),
    )
    op.add_column(
        'correcciones',
        sa.Column(
            'condicion_desaprobacion_aplicada',
            sa.Text(),
            nullable=True,
        ),
    )
    op.add_column(
        'correcciones',
        sa.Column(
            'penalizaciones_aplicadas',
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default='{}',
        ),
    )


def downgrade() -> None:
    op.drop_column('correcciones', 'penalizaciones_aplicadas')
    op.drop_column('correcciones', 'condicion_desaprobacion_aplicada')
    op.drop_column('correcciones', 'nota_antes_penalizaciones')
