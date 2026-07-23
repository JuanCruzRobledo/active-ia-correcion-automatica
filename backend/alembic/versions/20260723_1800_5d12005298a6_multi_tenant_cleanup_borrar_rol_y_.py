"""multi-tenant cleanup: borrar rol y moodle_* globales de usuarios

Fase 6 y ÚLTIMA del plan multi-tenant (multi-tenant-cleanup-rol-global).
Desde la Fase 0, `usuarios.rol`/`usuarios.moodle_{username,password_encrypted,
host}` convivían con sus reemplazos en `usuario_universidad`/`universidades`.
El código (routers, services, repositories) ya no lee ni escribe estas
columnas — verificado con la suite completa corriendo en verde ANTES de esta
migración (tarea 5.2 del change). Esta migración cierra la convivencia.

**Guard de `upgrade`**: aborta si encuentra algún usuario sin membresía
activa en `usuario_universidad` — ese usuario se quedaría sin rol. Verificado
contra la base real antes de escribir esta migración: 0 usuarios en esa
situación (56 usuarios, todos con membresía activa).

**`downgrade` con pérdida documentada**: recrea las 4 columnas y las
REPUEBLA (no las deja vacías) tomando, para cada usuario, la membresía
ACTIVA más antigua (menor `id` en `usuario_universidad`, que no tiene
`created_at`) — mismo criterio que usa el código para casos análogos
(`UsuarioRepository.get_rol_mas_antiguo`). `moodle_host` se toma de la
`Universidad` de esa misma membresía (es de ahí de donde vive hoy). Si una
persona tiene roles/credenciales DISTINTOS en varias universidades, el rol
global recuperado es el de la membresía más antigua — una convención, no una
recuperación fiel. Se documenta a propósito: un `downgrade` que revierte sin
perder un carácter no existe una vez que el modelo pasó a ser por-universidad.

Revision ID: 5d12005298a6
Revises: a71e5c9d3b82
Create Date: 2026-07-23 18:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "5d12005298a6"
down_revision: Union[str, None] = "a71e5c9d3b82"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- Guard: ningún usuario puede quedarse sin rol -------------------
    sin_membresia = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM usuarios u WHERE NOT EXISTS ("
            "    SELECT 1 FROM usuario_universidad uu "
            "    WHERE uu.usuario_id = u.id AND uu.activo = true"
            ")"
        )
    ).scalar_one()
    if sin_membresia:
        raise RuntimeError(
            f"multi-tenant cleanup: {sin_membresia} usuario(s) sin membresía "
            "activa en usuario_universidad. Abortando: borrar usuarios.rol "
            "los dejaría sin rol. Resolvé sus membresías antes de reintentar "
            "esta migración."
        )

    op.drop_index("ix_usuarios_rol", table_name="usuarios")
    op.drop_column("usuarios", "rol")
    op.drop_column("usuarios", "moodle_username")
    op.drop_column("usuarios", "moodle_password_encrypted")
    op.drop_column("usuarios", "moodle_host")


def downgrade() -> None:
    bind = op.get_bind()

    # rol_enum ya existe (lo crea la migración inicial; usuario_universidad.rol
    # lo sigue usando) — create_type=False para no intentar recrearlo.
    rol_enum = postgresql.ENUM(
        "ADMIN", "COORDINADOR", "TUTOR", "GESTOR", name="rol_enum", create_type=False
    )

    op.add_column("usuarios", sa.Column("rol", rol_enum, nullable=True))
    op.add_column(
        "usuarios", sa.Column("moodle_username", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "usuarios", sa.Column("moodle_password_encrypted", sa.Text(), nullable=True)
    )
    op.add_column(
        "usuarios", sa.Column("moodle_host", sa.String(length=255), nullable=True)
    )

    # Repuebla desde la membresía ACTIVA más antigua de cada usuario (D6):
    # `DISTINCT ON` (Postgres) se queda con la fila de menor `uu.id` por
    # usuario_id. `moodle_host` sale de la Universidad de esa membresía.
    bind.execute(
        sa.text(
            """
            WITH membresia_mas_antigua AS (
                SELECT DISTINCT ON (uu.usuario_id)
                    uu.usuario_id,
                    uu.rol,
                    uu.moodle_username,
                    uu.moodle_password_encrypted,
                    un.moodle_host
                FROM usuario_universidad uu
                JOIN universidades un ON un.id = uu.universidad_id
                WHERE uu.activo = true
                ORDER BY uu.usuario_id, uu.id ASC
            )
            UPDATE usuarios
               SET rol = m.rol,
                   moodle_username = m.moodle_username,
                   moodle_password_encrypted = m.moodle_password_encrypted,
                   moodle_host = m.moodle_host
              FROM membresia_mas_antigua m
             WHERE usuarios.id = m.usuario_id
            """
        )
    )

    # Guard simétrico al de `upgrade`: si algún usuario quedó sin rol (no
    # debería pasar — mismo invariante), abortar en vez de dejar una columna
    # NOT NULL con NULLs, que rompería el ALTER de abajo con un mensaje críptico.
    sin_rol = bind.execute(
        sa.text("SELECT COUNT(*) FROM usuarios WHERE rol IS NULL")
    ).scalar_one()
    if sin_rol:
        raise RuntimeError(
            f"multi-tenant cleanup downgrade: {sin_rol} usuario(s) sin ninguna "
            "membresía activa en usuario_universidad — no se puede repoblar "
            "usuarios.rol. Resolvé sus membresías antes de reintentar el downgrade."
        )

    op.alter_column("usuarios", "rol", nullable=False)
    op.create_index("ix_usuarios_rol", "usuarios", ["rol"], unique=False)
