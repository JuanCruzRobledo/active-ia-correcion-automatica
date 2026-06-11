"""add snapshot_cron_config (singleton del cron de snapshots)

Revision ID: 014_snapshot_cron_config
Revises: 013_avance_desaprobada
Create Date: 2026-06-03

Config del cron diario del Dashboard de Gestores: usuario (credenciales Moodle) +
hora/minuto + activo. Singleton (fila id=1). Ref: PLAN_DASHBOARD_GESTORES.md §7 (T6).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014_snapshot_cron_config"
down_revision: Union[str, None] = "013_avance_desaprobada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snapshot_cron_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("hora", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("minuto", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["usuario_id"], ["usuarios.id"],
            name=op.f("fk_snapshot_cron_config_usuario_id_usuarios"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_snapshot_cron_config")),
    )
    # Fila singleton inicial (inactiva, sin usuario, 03:00).
    op.execute(
        """
        INSERT INTO snapshot_cron_config (id, usuario_id, hora, minuto, activo, created_at, updated_at)
        VALUES (1, NULL, 3, 0, false, now(), now())
        ON CONFLICT (id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_table("snapshot_cron_config")
