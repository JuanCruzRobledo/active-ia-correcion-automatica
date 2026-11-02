"""Versionar análisis de archivos sin penalizar entregas existentes.

Revision ID: b219adce5108
Revises: f8b4d2e6c901
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b219adce5108"
down_revision = "f8b4d2e6c901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("entregas", "entregas_historial"):
        op.add_column(table, sa.Column("analisis_archivos", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    for table in ("entregas_historial", "entregas"):
        op.drop_column(table, "analisis_archivos")
