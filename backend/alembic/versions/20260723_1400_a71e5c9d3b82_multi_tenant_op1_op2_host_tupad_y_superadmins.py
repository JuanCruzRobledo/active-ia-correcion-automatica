"""multi-tenant OP-1 y OP-2: campus de TUPaD y superadmins iniciales

Cierra las dos precondiciones operativas que venían abiertas desde la Fase 3
del plan multi-tenant y que bloqueaban el despliegue:

**OP-1** — `Universidad.moodle_host` de TUPaD quedó en NULL cuando la Fase 0
migró los datos: en `usuarios.moodle_host` había TRES valores divergentes y la
migración prefirió dejarlo vacío antes que inventar uno. Este es el valor
autoritativo. Sin él, `moodle_credentials_resolver` corta con 424 y NINGUNA
operación contra Moodle funciona.

**OP-2** — todos los usuarios quedaron con `es_superadmin = false`, así que
nadie podía administrar universidades. Se otorga a tres cuentas concretas, no
a los 13 ADMIN: `es_superadmin` no es "admin con más permisos", es un bypass
que atraviesa TODOS los tenants (`permissions._acceso_total`), ve los datos de
todas las universidades y puede crear y dar de baja universidades. Los ADMIN
restantes conservan intactos sus permisos dentro de TUPaD.

Los usuarios se identifican por `username` y NO por id: `usuarios.username`
tiene índice único y es estable entre ambientes, mientras que un id puede
corresponder a otra persona en otra base. Una migración que otorga un bypass
global al usuario equivocado es un problema silencioso y grave.

Es idempotente: sólo escribe el host si está vacío, y sólo toca las filas cuyo
`username` coincide. Si una cuenta no existe en el ambiente destino, esa fila
simplemente no se actualiza y la migración no falla.

Revision ID: a71e5c9d3b82
Revises: c3f8a1d9b204
Create Date: 2026-07-23 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a71e5c9d3b82"
down_revision: Union[str, None] = "c3f8a1d9b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# El código arma las URLs con `moodle_host.rstrip("/")` (moodle_service.py), así
# que la barra final es inocua; se guarda el valor tal como lo dio el operador.
MOODLE_HOST_TUPAD = "http://tup.sied.utn.edu.ar/"

NOMBRE_TUPAD = "Tecnicatura Universitaria en Programación a Distancia"

SUPERADMINS = ("admin", "matytorres", "juancruzrobledo")


def upgrade() -> None:
    # --- OP-1: campus de TUPaD -------------------------------------------
    # Sólo si está vacío: si otro ambiente ya tiene un host cargado, no se pisa.
    op.execute(
        sa.text(
            """
            UPDATE universidades
               SET moodle_host = :host,
                   updated_at = now()
             WHERE nombre = :nombre
               AND (moodle_host IS NULL OR moodle_host = '')
            """
        ).bindparams(host=MOODLE_HOST_TUPAD, nombre=NOMBRE_TUPAD)
    )

    # --- OP-2: superadmins iniciales -------------------------------------
    op.execute(
        sa.text(
            """
            UPDATE usuarios
               SET es_superadmin = true,
                   updated_at = now()
             WHERE username IN :usernames
               AND es_superadmin = false
            """
        ).bindparams(sa.bindparam("usernames", value=SUPERADMINS, expanding=True))
    )


def downgrade() -> None:
    # OP-2: revocar el bypass global. Los usuarios conservan su rol de
    # membresía, sólo pierden el alcance cross-tenant.
    op.execute(
        sa.text(
            """
            UPDATE usuarios
               SET es_superadmin = false,
                   updated_at = now()
             WHERE username IN :usernames
            """
        ).bindparams(sa.bindparam("usernames", value=SUPERADMINS, expanding=True))
    )

    # OP-1: volver el campus a NULL, que es el estado que dejó la Fase 0.
    op.execute(
        sa.text(
            """
            UPDATE universidades
               SET moodle_host = NULL,
                   updated_at = now()
             WHERE nombre = :nombre
               AND moodle_host = :host
            """
        ).bindparams(host=MOODLE_HOST_TUPAD, nombre=NOMBRE_TUPAD)
    )
