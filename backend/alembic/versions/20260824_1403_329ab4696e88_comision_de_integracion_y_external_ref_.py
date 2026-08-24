"""comision de integracion y external_ref en comisiones

Revision ID: 329ab4696e88
Revises: 56a1724602e2
Create Date: 2026-08-24

Change: `correccion-por-ejercicio-con-tests`, bloque 1.

Resuelve el hueco que el pedido de AI-Native no podía ver, porque no ve nuestro
modelo de datos: **`entregas.comision_id` es NOT NULL y el cliente no tiene
comisiones**. Sin esto, el endpoint de corrección por ejercicio no puede
persistir absolutamente nada.

Dos columnas, en orden de precedencia de uso:

1. `comisiones.external_ref` — para el cliente que quiera modelar sus cohortes.
2. `materias.comision_integracion_id` — la comisión que un admin configura UNA
   VEZ por materia al dar de alta la integración, y donde caen todas las
   entregas externas si el cliente no manda cohorte.

Ambas son NULLABLE y aditivas: el flujo de Moodle no las usa ni se entera.

**Alternativa descartada**: volver nullable `entregas.comision_id`. Es una tabla
caliente, con índices, scoping multi-tenant y consultas en medio proyecto que
asumen la comisión. Esa nullabilidad se paga para siempre; estas dos columnas de
configuración se pagan una vez.

Escrita a mano y NO con `--autogenerate` a propósito: el autogenerate de este
repo arrastra drift preexistente entre los modelos y la base (comments, server
defaults, el FK de `moodle_sync` sin su `ondelete`, el único de
`universidades.nombre`). Ver la nota de la migración 56a1724602e2. Ese drift es
un hallazgo aparte y merece su propio change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '329ab4696e88'
down_revision: Union[str, None] = '56a1724602e2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. comisiones.external_ref -------------------------------------------
    op.add_column(
        'comisiones', sa.Column('external_ref', sa.String(length=64), nullable=True)
    )
    # Parcial sobre no nulos: la enorme mayoría de las comisiones (las de Moodle)
    # no tienen identificador externo, y varios NULL no deben colisionar entre sí.
    op.create_index(
        'uq_comision_materia_external_ref',
        'comisiones',
        ['materia_id', 'external_ref'],
        unique=True,
        postgresql_where=sa.text('external_ref IS NOT NULL'),
    )

    # --- 2. materias.comision_integracion_id ----------------------------------
    op.add_column(
        'materias', sa.Column('comision_integracion_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        op.f('fk_materias_comision_integracion_id_comisiones'),
        'materias', 'comisiones', ['comision_integracion_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('fk_materias_comision_integracion_id_comisiones'),
        'materias', type_='foreignkey',
    )
    op.drop_column('materias', 'comision_integracion_id')

    op.drop_index('uq_comision_materia_external_ref', table_name='comisiones')
    op.drop_column('comisiones', 'external_ref')
