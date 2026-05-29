"""Add modo_consolidacion to rubrica (Fase 2)

Revision ID: 011_modo_consolidacion
Revises: 010_moodle_bidireccional
Create Date: 2026-05-29

Permite configurar por rúbrica cómo se consolida el código de las entregas
(solo_codigo / web_completo / proyecto_completo / personalizado). Lo usa la
importación desde Moodle (automática) para no aplicar siempre 'solo_codigo'.

Columnas nuevas (sin backfill destructivo):
- rubricas.modo_consolidacion  : NOT NULL, server_default 'solo_codigo'.
- rubricas.extensiones_personalizadas : ARRAY(varchar) nullable (modo personalizado).

Ref: PLAN_FEAT.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '011_modo_consolidacion'
down_revision: Union[str, None] = '010_moodle_bidireccional'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, 'rubricas', 'modo_consolidacion'):
        op.add_column(
            'rubricas',
            sa.Column(
                'modo_consolidacion',
                sa.String(length=30),
                nullable=False,
                server_default='solo_codigo',
            ),
        )
    if not _column_exists(conn, 'rubricas', 'extensiones_personalizadas'):
        op.add_column(
            'rubricas',
            sa.Column('extensiones_personalizadas', sa.ARRAY(sa.String()), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, 'rubricas', 'extensiones_personalizadas'):
        op.drop_column('rubricas', 'extensiones_personalizadas')
    if _column_exists(conn, 'rubricas', 'modo_consolidacion'):
        op.drop_column('rubricas', 'modo_consolidacion')
