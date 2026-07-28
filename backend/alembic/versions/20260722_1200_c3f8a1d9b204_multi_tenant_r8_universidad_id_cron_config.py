"""multi-tenant R8: universidad_id en la config de los crons (Fase 3)

Revision ID: c3f8a1d9b204
Revises: 103ac75da627
Create Date: 2026-07-22 12:00:00.000000

Fase 3 del feature multi-tenant (openspec/changes/multi-tenant-moodle-services,
OQ2): los crons de notificaciones y snapshots corren SIN request/ctx (no hay
JWT del que leer `universidad_activa_id`), así que la universidad activa para
esos jobs pasa a vivir en su propia fila de config, junto al `usuario_id` de
servicio que ya tenían.

Agrega `universidad_id` (FK -> universidades, NULLABLE) a
`notificacion_cron_config` y `snapshot_cron_config`, y backfillea las filas
EXISTENTES a TUPaD (única universidad hoy). Se mantiene nullable a nivel DB
—mismo patrón que la columna `usuario_id` de esas tablas (singleton que puede
empezar sin configurar)—: el service exige AMBOS (usuario_id + universidad_id)
recién al ACTIVAR el cron (`NotificacionConfigService`/`SnapshotConfigService
.actualizar`), no a nivel de constraint. Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3f8a1d9b204'
down_revision: Union[str, None] = '103ac75da627'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NOMBRE_TUPAD = "Tecnicatura Universitaria en Programación a Distancia"
TABLAS = ["notificacion_cron_config", "snapshot_cron_config"]


def upgrade() -> None:
    bind = op.get_bind()

    for tabla in TABLAS:
        op.add_column(
            tabla,
            sa.Column("universidad_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{tabla}_universidad_id",
            tabla,
            "universidades",
            ["universidad_id"],
            ["id"],
        )

    id_tupad = bind.execute(
        sa.text("SELECT id FROM universidades WHERE nombre = :nombre"),
        {"nombre": NOMBRE_TUPAD},
    ).scalar_one_or_none()

    # Sin TUPaD seedeada (entorno sin Fase 0 corrida todavía) no hay nada para
    # backfillear: la columna queda agregada y NULL, sin abortar la migración
    # (a diferencia de R5/R7, acá el backfill es una comodidad, no un invariante
    # estructural — la columna es nullable a propósito, ver docstring).
    if id_tupad is not None:
        for tabla in TABLAS:
            bind.execute(
                sa.text(
                    f"UPDATE {tabla} SET universidad_id = :id WHERE universidad_id IS NULL"
                ),
                {"id": id_tupad},
            )


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        op.drop_constraint(f"fk_{tabla}_universidad_id", tabla, type_="foreignkey")
        op.drop_column(tabla, "universidad_id")
