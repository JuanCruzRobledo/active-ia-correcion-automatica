"""multi-tenant R6: backfill de membresías usuario_universidad (data migration)

Revision ID: ea7c83500aac
Revises: e2d06591ae29
Create Date: 2026-07-22 10:50:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R6 de 7: por cada `Usuario` existente, crea exactamente una membresía en
`usuario_universidad` para TUPaD, copiando tal cual (sin descifrar/re-cifrar)
su `rol`, `moodle_username` y `moodle_password_encrypted` actuales, con
`activo = true`. Idempotente respecto al `UniqueConstraint(usuario_id,
universidad_id)` vía `NOT EXISTS`. OP-2 (es_superadmin): el backfill NO
promueve a nadie — todos quedan en `false` (columna con default en R3); la
promoción de superadmin(es) es un paso operativo manual posterior (tasks.md
10.2), deliberadamente fuera de esta migración. Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'ea7c83500aac'
down_revision: Union[str, None] = 'e2d06591ae29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_TUPAD = "Tecnicatura Universitaria en Programación a Distancia"


def upgrade() -> None:
    bind = op.get_bind()

    id_tupad = bind.execute(
        sa.text("SELECT id FROM universidades WHERE nombre = :nombre"),
        {"nombre": NOMBRE_TUPAD},
    ).scalar_one()

    bind.execute(
        sa.text(
            "INSERT INTO usuario_universidad "
            "(usuario_id, universidad_id, rol, moodle_username, "
            " moodle_password_encrypted, activo) "
            "SELECT u.id, :id_tupad, u.rol, u.moodle_username, "
            "       u.moodle_password_encrypted, true "
            "FROM usuarios u "
            "WHERE NOT EXISTS ("
            "    SELECT 1 FROM usuario_universidad uu "
            "    WHERE uu.usuario_id = u.id AND uu.universidad_id = :id_tupad"
            ")"
        ),
        {"id_tupad": id_tupad},
    )

    # Red de seguridad: exactamente una membresía TUPaD por usuario.
    faltantes = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM usuarios u WHERE NOT EXISTS ("
            "    SELECT 1 FROM usuario_universidad uu "
            "    WHERE uu.usuario_id = u.id AND uu.universidad_id = :id_tupad"
            ")"
        ),
        {"id_tupad": id_tupad},
    ).scalar_one()
    if faltantes:
        raise RuntimeError(
            f"multi-tenant R6: {faltantes} usuario(s) sin membresía TUPaD tras el backfill."
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM usuario_universidad WHERE universidad_id = ("
            "    SELECT id FROM universidades WHERE nombre = :nombre"
            ")"
        ),
        {"nombre": NOMBRE_TUPAD},
    )
