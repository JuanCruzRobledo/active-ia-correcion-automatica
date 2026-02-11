"""Remove activo field from entregas

Revision ID: 002_remove_activo_entregas
Revises: 001_initial
Create Date: 2026-02-11

Removes soft delete functionality from entregas table:
- Drops partial unique index uq_entrega_rubrica_alumno_activo
- Drops activo column index
- Drops activo column
- Creates new simple unique index on (rubrica_id, alumno_nombre)

This change moves entregas from soft delete to hard delete,
as discussed in the architecture review for transactional data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_remove_activo_entregas'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the partial unique index
    op.drop_index('uq_entrega_rubrica_alumno_activo', table_name='entregas')

    # Drop the activo column index
    op.drop_index(op.f('ix_entregas_activo'), table_name='entregas')

    # Drop the activo column
    op.drop_column('entregas', 'activo')

    # Create new simple unique index (not partial)
    op.create_index(
        'uq_entrega_rubrica_alumno',
        'entregas',
        ['rubrica_id', 'alumno_nombre'],
        unique=True
    )


def downgrade() -> None:
    # Drop the new simple unique index
    op.drop_index('uq_entrega_rubrica_alumno', table_name='entregas')

    # Re-add the activo column
    op.add_column(
        'entregas',
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true')
    )

    # Re-create the activo column index
    op.create_index(op.f('ix_entregas_activo'), 'entregas', ['activo'], unique=False)

    # Re-create the partial unique index
    op.create_index(
        'uq_entrega_rubrica_alumno_activo',
        'entregas',
        ['rubrica_id', 'alumno_nombre'],
        unique=True,
        postgresql_where=sa.text('activo = true')
    )
