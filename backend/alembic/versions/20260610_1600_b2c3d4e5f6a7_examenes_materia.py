"""examenes materia (seguimiento de examenes)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-10 16:00:00.000000

Crea la tabla examenes_materia (parciales/recuperatorios/extensiones/extraordinarias/
globales por materia) + sus enums. recupera_examen_id es self-FK al PARCIAL que rescata.
Escrita a mano para controlar la creación de los enums.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tipo_enum = postgresql.ENUM(
        'PARCIAL', 'RECUPERATORIO', 'EXTENSION', 'EXTRAORDINARIA', 'GLOBAL',
        name='tipoexamenenum',
    )
    modo_enum = postgresql.ENUM('ESCALA', 'NUMERICO', name='modoaprobacionenum')
    tipo_enum.create(bind, checkfirst=True)
    modo_enum.create(bind, checkfirst=True)

    op.create_table(
        'examenes_materia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            postgresql.ENUM(name='tipoexamenenum', create_type=False),
            nullable=False,
        ),
        sa.Column(
            'moodle_cmid', sa.Integer(), nullable=False,
            comment='cmid de la actividad de Moodle del examen',
        ),
        sa.Column(
            'modo_aprobacion',
            postgresql.ENUM(name='modoaprobacionenum', create_type=False),
            nullable=False,
            comment='ESCALA (Aprobado/Desaprobado) | NUMERICO (nota >= nota_minima)',
        ),
        sa.Column(
            'nota_minima', sa.Float(), nullable=True,
            comment='Mínimo para aprobar (solo si modo NUMERICO)',
        ),
        sa.Column(
            'recupera_examen_id', sa.Integer(), nullable=True,
            comment='PARCIAL que recupera (solo recuperatorio/extensión/extraordinaria)',
        ),
        sa.Column(
            'orden', sa.Integer(), server_default='0', nullable=False,
            comment='Orden de alta; deriva el número visible por tipo (Parcial 1, 2…)',
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['recupera_examen_id'], ['examenes_materia.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_examenes_materia_id'), 'examenes_materia', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_examenes_materia_materia_id'),
        'examenes_materia', ['materia_id'], unique=False,
    )
    op.create_index(
        op.f('ix_examenes_materia_recupera_examen_id'),
        'examenes_materia', ['recupera_examen_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_examenes_materia_recupera_examen_id'), table_name='examenes_materia'
    )
    op.drop_index(op.f('ix_examenes_materia_materia_id'), table_name='examenes_materia')
    op.drop_index(op.f('ix_examenes_materia_id'), table_name='examenes_materia')
    op.drop_table('examenes_materia')

    bind = op.get_bind()
    sa.Enum(name='modoaprobacionenum').drop(bind, checkfirst=True)
    sa.Enum(name='tipoexamenenum').drop(bind, checkfirst=True)
