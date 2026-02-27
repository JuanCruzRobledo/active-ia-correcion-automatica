"""Make subido_por_id and corregido_por_id nullable for hard delete support

Revision ID: 006_nullable_fk_hard_delete
Revises: 005_add_pdf_b64_entregas
Create Date: 2026-02-27

When ALLOW_HARD_DELETE=true, deleting a Usuario must not cascade-delete
the Entrega and Correccion records they uploaded/reviewed (those records
belong to the students/subject, not to the user).
To achieve this, we SET NULL on these FK columns before deleting the user.
This migration makes those columns nullable in the DB.

Affected columns:
  - entregas.subido_por_id  (FK → usuarios.id)  NOT NULL → NULL
  - correcciones.corregido_por_id  (FK → usuarios.id)  NOT NULL → NULL

Ref: plan_hard_delete.md
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_nullable_fk_hard_delete'
down_revision: Union[str, None] = '005_add_pdf_b64_entregas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make entregas.subido_por_id nullable
    op.alter_column(
        'entregas',
        'subido_por_id',
        existing_type=sa.Integer(),
        nullable=True,
    )

    # Make correcciones.corregido_por_id nullable
    op.alter_column(
        'correcciones',
        'corregido_por_id',
        existing_type=sa.Integer(),
        nullable=True,
    )


def downgrade() -> None:
    # Revert correcciones.corregido_por_id to NOT NULL
    # Note: this will fail if there are NULL values in the column
    op.alter_column(
        'correcciones',
        'corregido_por_id',
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Revert entregas.subido_por_id to NOT NULL
    # Note: this will fail if there are NULL values in the column
    op.alter_column(
        'entregas',
        'subido_por_id',
        existing_type=sa.Integer(),
        nullable=False,
    )
