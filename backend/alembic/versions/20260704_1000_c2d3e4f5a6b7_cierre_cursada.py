"""cierre de cursada: items, runs, alumnos

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-07-04 10:00:00.000000

Persiste el cierre de cursada (PROMOCIONA/REGULARIZA/RECURSA) generado desde
el admin panel: el mapeo confirmado de ítems del calificador de Moodle
(cierre_cursada_items), la cabecera de cada corrida (cierre_cursada_runs,
append-only) y el veredicto + datos crudos de auditoría por alumno
(cierre_cursada_alumnos). Escrita a mano, mismo estilo que las migraciones
recientes (sa.Enum inline en la columna + DROP TYPE explícito en downgrade).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cierre_cursada_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('cuatrimestre_id', sa.Integer(), nullable=False),
        sa.Column('moodle_cmid', sa.Integer(), nullable=False),
        sa.Column('nombre_moodle', sa.String(length=255), nullable=False),
        sa.Column(
            'categoria',
            sa.Enum('TP', 'AUTOEVAL', 'PARCIAL_1', 'PARCIAL_2', 'TPI', 'IGNORAR',
                    name='categoriaitemcierreenum'),
            nullable=False,
        ),
        sa.Column('unidad', sa.Integer(), nullable=True,
                  comment='Número de unidad (TP/AUTOEVAL); NULL para PARCIAL/TPI/IGNORAR'),
        sa.Column('opcional', sa.Boolean(), nullable=False, server_default='false',
                  comment='Excluida del denominador de tp_ok/autoeval_ok (ej. Unidad 9/10)'),
        sa.Column('orden', sa.Integer(), nullable=True,
                  comment='Orden real en el curso de Moodle, para la UI de revisión'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'],
                                 name=op.f('fk_cierre_cursada_items_materia_id_materias')),
        sa.ForeignKeyConstraint(['cuatrimestre_id'], ['cuatrimestres.id'],
                                 name=op.f('fk_cierre_cursada_items_cuatrimestre_id_cuatrimestres')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cierre_cursada_items')),
        sa.UniqueConstraint('materia_id', 'cuatrimestre_id', 'moodle_cmid',
                             name='uq_cierre_item_materia_cuatri_cmid'),
    )
    op.create_index(op.f('ix_cierre_cursada_items_id'), 'cierre_cursada_items', ['id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_items_materia_id'), 'cierre_cursada_items', ['materia_id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_items_cuatrimestre_id'), 'cierre_cursada_items', ['cuatrimestre_id'], unique=False)

    op.create_table(
        'cierre_cursada_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('cuatrimestre_id', sa.Integer(), nullable=False),
        sa.Column('umbral_tp_pct', sa.Float(), nullable=False,
                  comment='% mínimo de TPs aprobados, ingresado por el usuario en esta corrida'),
        sa.Column('reglas_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False,
                  comment='Umbrales CONGELADOS al momento de la corrida — reproducibilidad histórica'),
        sa.Column('generado_por_id', sa.Integer(), nullable=False),
        sa.Column('total_alumnos', sa.Integer(), nullable=False),
        sa.Column('total_promociona', sa.Integer(), nullable=False),
        sa.Column('total_regulariza', sa.Integer(), nullable=False),
        sa.Column('total_recursa', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'],
                                 name=op.f('fk_cierre_cursada_runs_materia_id_materias')),
        sa.ForeignKeyConstraint(['cuatrimestre_id'], ['cuatrimestres.id'],
                                 name=op.f('fk_cierre_cursada_runs_cuatrimestre_id_cuatrimestres')),
        sa.ForeignKeyConstraint(['generado_por_id'], ['usuarios.id'],
                                 name=op.f('fk_cierre_cursada_runs_generado_por_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cierre_cursada_runs')),
    )
    op.create_index(op.f('ix_cierre_cursada_runs_id'), 'cierre_cursada_runs', ['id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_runs_materia_id'), 'cierre_cursada_runs', ['materia_id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_runs_cuatrimestre_id'), 'cierre_cursada_runs', ['cuatrimestre_id'], unique=False)

    op.create_table(
        'cierre_cursada_alumnos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('moodle_user_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=True),
        sa.Column('apellido', sa.String(length=100), nullable=True),
        sa.Column('email', sa.String(length=150), nullable=True),
        sa.Column('comision_id', sa.Integer(), nullable=True),
        sa.Column('comision_nombre', sa.String(length=100), nullable=True,
                  comment="Denormalizado: 'Sin comisión asignada' si no matcheó ningún grupo"),
        sa.Column('tutor_nombre', sa.String(length=200), nullable=True),
        sa.Column('tps', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('autoeval_pcts', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('parcial1_instancias', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('parcial2_instancias', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tpi_instancias', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('tp_ok', sa.Boolean(), nullable=False),
        sa.Column('autoeval_ok', sa.Boolean(), nullable=False),
        sa.Column('p1_max', sa.Float(), nullable=True),
        sa.Column('p2_max', sa.Float(), nullable=True),
        sa.Column('tpi_max', sa.Float(), nullable=True),
        sa.Column('estado', sa.Enum('PROMOCIONA', 'REGULARIZA', 'RECURSA', name='estadocierreenum'),
                  nullable=False),
        sa.Column('nota_final', sa.Integer(), nullable=True,
                  comment="0-10, solo si PROMOCIONA; None = 'N/E' en el reporte"),
        sa.Column('habilitado_final', sa.String(length=60), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['cierre_cursada_runs.id'],
                                 name=op.f('fk_cierre_cursada_alumnos_run_id_cierre_cursada_runs')),
        sa.ForeignKeyConstraint(['comision_id'], ['comisiones.id'],
                                 name=op.f('fk_cierre_cursada_alumnos_comision_id_comisiones')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_cierre_cursada_alumnos')),
    )
    op.create_index(op.f('ix_cierre_cursada_alumnos_id'), 'cierre_cursada_alumnos', ['id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_alumnos_run_id'), 'cierre_cursada_alumnos', ['run_id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_alumnos_moodle_user_id'), 'cierre_cursada_alumnos', ['moodle_user_id'], unique=False)
    op.create_index(op.f('ix_cierre_cursada_alumnos_estado'), 'cierre_cursada_alumnos', ['estado'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_cierre_cursada_alumnos_estado'), table_name='cierre_cursada_alumnos')
    op.drop_index(op.f('ix_cierre_cursada_alumnos_moodle_user_id'), table_name='cierre_cursada_alumnos')
    op.drop_index(op.f('ix_cierre_cursada_alumnos_run_id'), table_name='cierre_cursada_alumnos')
    op.drop_index(op.f('ix_cierre_cursada_alumnos_id'), table_name='cierre_cursada_alumnos')
    op.drop_table('cierre_cursada_alumnos')

    op.drop_index(op.f('ix_cierre_cursada_runs_cuatrimestre_id'), table_name='cierre_cursada_runs')
    op.drop_index(op.f('ix_cierre_cursada_runs_materia_id'), table_name='cierre_cursada_runs')
    op.drop_index(op.f('ix_cierre_cursada_runs_id'), table_name='cierre_cursada_runs')
    op.drop_table('cierre_cursada_runs')

    op.drop_index(op.f('ix_cierre_cursada_items_cuatrimestre_id'), table_name='cierre_cursada_items')
    op.drop_index(op.f('ix_cierre_cursada_items_materia_id'), table_name='cierre_cursada_items')
    op.drop_index(op.f('ix_cierre_cursada_items_id'), table_name='cierre_cursada_items')
    op.drop_table('cierre_cursada_items')

    # Los tipos enum nativos de PG no se eliminan al dropear la tabla → limpiarlos.
    op.execute("DROP TYPE IF EXISTS estadocierreenum")
    op.execute("DROP TYPE IF EXISTS categoriaitemcierreenum")
