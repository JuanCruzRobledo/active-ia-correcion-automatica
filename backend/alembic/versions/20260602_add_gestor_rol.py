"""Add GESTOR value to rol_enum

Revision ID: 012_add_gestor_rol
Revises: 011_modo_consolidacion
Create Date: 2026-06-02

Agrega el rol GESTOR al enum nativo de PostgreSQL `rol_enum` para la pantalla
"Gestión" (reportes de usuarios de Moodle).

Nota: `ALTER TYPE ... ADD VALUE` no puede correr dentro de un bloque de
transacción en varias versiones de PostgreSQL. Usamos `autocommit_block()`
(API oficial de Alembic) en vez de un COMMIT manual.
"""

from typing import Sequence, Union

from alembic import op

revision: str = '012_add_gestor_rol'
down_revision: Union[str, None] = '011_modo_consolidacion'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS → idempotente (re-correr la migración no rompe).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE rol_enum ADD VALUE IF NOT EXISTS 'GESTOR'")


def downgrade() -> None:
    # PostgreSQL no permite DROP VALUE en un enum: recreamos el tipo sin 'GESTOR'.
    # El cast `rol::text::rol_enum` FALLA a propósito si algún usuario tiene rol
    # GESTOR, para no perder datos en silencio (habría que reasignar esos usuarios
    # antes de revertir).
    op.execute("ALTER TYPE rol_enum RENAME TO rol_enum_old")
    op.execute("CREATE TYPE rol_enum AS ENUM ('ADMIN', 'COORDINADOR', 'TUTOR')")
    op.execute(
        "ALTER TABLE usuarios ALTER COLUMN rol TYPE rol_enum "
        "USING rol::text::rol_enum"
    )
    op.execute("DROP TYPE rol_enum_old")
