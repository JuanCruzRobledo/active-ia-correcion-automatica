"""materia etiqueta_unidad (Unidad/Semana) para reportes

Revision ID: a1b2c3d4e5f6
Revises: d6352d492298
Create Date: 2026-06-08 15:00:00.000000

Permite que cada materia configure cómo se llama su progresión en los reportes
(Excel/PDF/emails): 'Unidad' (default) o 'Semana' (caso PYE, organizada por semanas).
"""

from alembic import op
import sqlalchemy as sa


revision = "a1b2c3d4e5f6"
down_revision = "d6352d492298"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "materias",
        sa.Column(
            "etiqueta_unidad",
            sa.String(length=20),
            nullable=False,
            server_default="Unidad",
        ),
    )


def downgrade() -> None:
    op.drop_column("materias", "etiqueta_unidad")
