"""Add pdf_contenido_b64 column to entregas

Revision ID: 005_add_pdf_b64_entregas
Revises: 004_fix_actividades_timestamps
Create Date: 2026-02-20

Adds a nullable Text column to store PDF submission content encoded
in Base64. This column is populated only when archivo_tipo='pdf',
allowing the correction service to send the raw PDF to the dedicated
N8N workflow (/webhook/corregir-pdf) instead of the text-based one.

Ref: docs/PLAN-SOPORTE-PDF-ENTREGAS.md Fase 1
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '005_add_pdf_b64_entregas'
down_revision: Union[str, None] = '004_fix_actividades_timestamps'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add pdf_contenido_b64 column to entregas table.
    # Nullable because existing entregas (ZIP/TXT/code) don't have PDF content.
    op.add_column(
        'entregas',
        sa.Column('pdf_contenido_b64', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    # Remove pdf_contenido_b64 column from entregas table
    op.drop_column('entregas', 'pdf_contenido_b64')
