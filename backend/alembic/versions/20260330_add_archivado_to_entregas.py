"""Add archivado column to entregas for archive/hide feature

Revision ID: 007_add_archivado_to_entregas
Revises: 006_nullable_fk_hard_delete
Create Date: 2026-03-30

Adds a boolean column `archivado` to entregas. Archived entregas are
hidden from the default list view and only shown when the estado filter
is set to "TODOS" (include_archivadas=true). This is a reversible display
preference — not a deletion. The unique constraint (rubrica_id, alumno_nombre)
is unchanged.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '007_add_archivado_to_entregas'
down_revision: Union[str, None] = '006_nullable_fk_hard_delete'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'entregas',
        sa.Column(
            'archivado',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.create_index('ix_entregas_archivado', 'entregas', ['archivado'])


def downgrade() -> None:
    op.drop_index('ix_entregas_archivado', table_name='entregas')
    op.drop_column('entregas', 'archivado')
