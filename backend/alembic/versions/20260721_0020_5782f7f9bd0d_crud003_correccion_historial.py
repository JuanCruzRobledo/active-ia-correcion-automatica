"""CRUD-003: tabla correccion_historial + tipo de auditoria CORRECCION_RECORREGIDA

Revision ID: 5782f7f9bd0d
Revises: c1a2b3d4e5f6
Create Date: 2026-07-21 00:20:59.262804

Hallazgo CRUD-003 (docs/auditoria/02-cruds.md): al recorregir, la corrección
anterior se borraba (hard delete) sin dejar rastro — se perdían nota anterior,
criterios, raw_response y las ediciones manuales. Ante un reclamo académico no
había forma de reconstruir qué pasó.

Se agrega `correccion_historial` (append-only): cada recorrección snapshotea la
corrección saliente ANTES de borrarla. El unique(entrega_id) de correcciones
impide dejar la vieja soft-deleted, por eso una tabla dedicada.

NOTA: el autogenerate capturó ADEMÁS mucho drift preexistente ajeno (cambios de
comentarios por acentos en cierre_cursada/materias/avance_alumnos y un
drop/recreate del FK de moodle_sync que le sacaba el ondelete). TODO eso se
descartó a mano: esta migración crea SOLO la tabla nueva y agrega el valor de enum.

El enum tipoactividadenum es nativo de Postgres (Actividad.tipo usa
SQLEnum(create_type=False)), así que el ADD VALUE va a mano (autogenerate no lo
detecta), igual que en c1a2b3d4e5f6. IF NOT EXISTS = idempotente. El downgrade
dropea la tabla; el valor de enum queda huérfano (Postgres no soporta DROP VALUE),
inocuo.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5782f7f9bd0d'
down_revision: Union[str, None] = 'c1a2b3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'correccion_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entrega_id', sa.Integer(), nullable=False),
        sa.Column('nota', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('criterios_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fortalezas', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('recomendaciones', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('comentario_general', sa.Text(), nullable=True),
        sa.Column('nota_antes_penalizaciones', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('condicion_desaprobacion_aplicada', sa.Text(), nullable=True),
        sa.Column('penalizaciones_aplicadas', sa.ARRAY(sa.Text()), server_default='{}', nullable=False),
        sa.Column('editado_manualmente', sa.Boolean(), nullable=False),
        sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('corregido_por_id', sa.Integer(), nullable=True),
        sa.Column('correccion_creada_en', sa.DateTime(), nullable=False),
        sa.Column('reemplazada_en', sa.DateTime(), nullable=False),
        sa.Column('reemplazada_por_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['corregido_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reemplazada_por_id'], ['usuarios.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_correccion_historial_entrega_id'),
        'correccion_historial', ['entrega_id'], unique=False,
    )
    op.create_index(
        op.f('ix_correccion_historial_id'),
        'correccion_historial', ['id'], unique=False,
    )
    op.execute("ALTER TYPE tipoactividadenum ADD VALUE IF NOT EXISTS 'CORRECCION_RECORREGIDA'")


def downgrade() -> None:
    op.drop_index(op.f('ix_correccion_historial_id'), table_name='correccion_historial')
    op.drop_index(op.f('ix_correccion_historial_entrega_id'), table_name='correccion_historial')
    op.drop_table('correccion_historial')
    # El valor CORRECCION_RECORREGIDA queda en el ENUM (Postgres no soporta DROP VALUE).
