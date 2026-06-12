"""componente calificacion modo y nota minima

Revision ID: af527d2fc7a0
Revises: 870c3f7ebcc9
Create Date: 2026-06-12 15:19:17.725278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'af527d2fc7a0'
down_revision: Union[str, None] = '870c3f7ebcc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Para componentes por CALIFICACION: cómo se interpreta la nota.
    # modoaprobacionenum YA existe (lo creó la migración de exámenes) → create_type=False.
    modo_enum = postgresql.ENUM(
        'ESCALA', 'NUMERICO', name='modoaprobacionenum', create_type=False
    )
    op.add_column(
        'componentes_unidad',
        sa.Column(
            'modo_aprobacion', modo_enum, nullable=False, server_default='ESCALA',
            comment='ESCALA (Aprobado/Desaprobado) | NUMERICO (nota >= nota_minima). Solo CALIFICACION',
        ),
    )
    op.add_column(
        'componentes_unidad',
        sa.Column(
            'nota_minima', sa.Float(), nullable=True,
            comment='Nota mínima para aprobar si modo_aprobacion=NUMERICO (escala de Moodle, ej. 6 o 60)',
        ),
    )


def downgrade() -> None:
    op.drop_column('componentes_unidad', 'nota_minima')
    op.drop_column('componentes_unidad', 'modo_aprobacion')
