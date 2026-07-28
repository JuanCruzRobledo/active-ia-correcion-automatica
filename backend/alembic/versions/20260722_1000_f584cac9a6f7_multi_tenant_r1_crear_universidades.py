"""multi-tenant R1: crear tabla universidades

Revision ID: f584cac9a6f7
Revises: d6f0e4a2b8c1
Create Date: 2026-07-22 10:00:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R1 de 7: crea la tabla `universidades` (tenant de primer nivel), sin tocar
ninguna tabla existente. Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f584cac9a6f7'
down_revision: Union[str, None] = 'd6f0e4a2b8c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'universidades',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('moodle_host', sa.String(length=255), nullable=True),
        sa.Column(
            'activa', sa.Boolean(), nullable=False, server_default=sa.text('true'),
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_universidades')),
        sa.UniqueConstraint('nombre', name=op.f('uq_universidades_nombre')),
    )
    op.create_index(op.f('ix_universidades_id'), 'universidades', ['id'], unique=False)
    op.create_index(op.f('ix_universidades_nombre'), 'universidades', ['nombre'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_universidades_nombre'), table_name='universidades')
    op.drop_index(op.f('ix_universidades_id'), table_name='universidades')
    op.drop_table('universidades')
