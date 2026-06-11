"""componentes unidad dinamicos

Revision ID: d6352d492298
Revises: 23e454a59b3f
Create Date: 2026-06-07 18:29:27.460611

§9.bis F — Pasa de 3 cmids fijos por unidad (moodle_tp/autoeval/cierre_cmid) a N
componentes dinámicos (tabla componentes_unidad con tipo + fuente + cmid). Convierte
los datos existentes y luego dropea las 3 columnas. Escrita a mano (sin autogenerate)
para incluir la migración de datos y evitar el drift de moodle_sync.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd6352d492298'
down_revision: Union[str, None] = '23e454a59b3f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tipo_enum = postgresql.ENUM(
        'TP', 'QUIZ', 'AUTOEVALUACION', 'CIERRE', name='tipocomponenteenum'
    )
    fuente_enum = postgresql.ENUM(
        'SEGUIMIENTO', 'CALIFICACION', name='fuentecomponenteenum'
    )
    tipo_enum.create(bind, checkfirst=True)
    fuente_enum.create(bind, checkfirst=True)

    op.create_table(
        'componentes_unidad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('unidad_id', sa.Integer(), nullable=False),
        sa.Column(
            'tipo',
            postgresql.ENUM(name='tipocomponenteenum', create_type=False),
            nullable=False,
        ),
        sa.Column(
            'moodle_cmid', sa.Integer(), nullable=False,
            comment='cmid de la actividad de Moodle vinculada',
        ),
        sa.Column(
            'fuente',
            postgresql.ENUM(name='fuentecomponenteenum', create_type=False),
            nullable=False,
            comment='SEGUIMIENTO (completion) | CALIFICACION (nota)',
        ),
        sa.Column(
            'orden', sa.Integer(), server_default='0', nullable=False,
            comment='Orden de presentación dentro de la unidad',
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['unidad_id'], ['unidades.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_componentes_unidad_id'), 'componentes_unidad', ['id'], unique=False
    )
    op.create_index(
        op.f('ix_componentes_unidad_unidad_id'),
        'componentes_unidad', ['unidad_id'], unique=False,
    )

    # --- Migración de datos: los 3 cmids fijos pasan a ser filas. ---
    # TP por CALIFICACIÓN (E7); autoeval/cierre por SEGUIMIENTO.
    op.execute(
        "INSERT INTO componentes_unidad "
        "(unidad_id, tipo, moodle_cmid, fuente, orden, created_at, updated_at) "
        "SELECT id, 'TP'::tipocomponenteenum, moodle_tp_cmid, "
        "'CALIFICACION'::fuentecomponenteenum, 0, now(), now() "
        "FROM unidades WHERE moodle_tp_cmid IS NOT NULL"
    )
    op.execute(
        "INSERT INTO componentes_unidad "
        "(unidad_id, tipo, moodle_cmid, fuente, orden, created_at, updated_at) "
        "SELECT id, 'AUTOEVALUACION'::tipocomponenteenum, moodle_autoeval_cmid, "
        "'SEGUIMIENTO'::fuentecomponenteenum, 1, now(), now() "
        "FROM unidades WHERE moodle_autoeval_cmid IS NOT NULL"
    )
    op.execute(
        "INSERT INTO componentes_unidad "
        "(unidad_id, tipo, moodle_cmid, fuente, orden, created_at, updated_at) "
        "SELECT id, 'CIERRE'::tipocomponenteenum, moodle_cierre_cmid, "
        "'SEGUIMIENTO'::fuentecomponenteenum, 2, now(), now() "
        "FROM unidades WHERE moodle_cierre_cmid IS NOT NULL"
    )

    op.drop_column('unidades', 'moodle_cierre_cmid')
    op.drop_column('unidades', 'moodle_autoeval_cmid')
    op.drop_column('unidades', 'moodle_tp_cmid')


def downgrade() -> None:
    op.add_column(
        'unidades',
        sa.Column(
            'moodle_tp_cmid', sa.Integer(), nullable=True,
            comment='cmid del TP/entregable (assign) de la unidad',
        ),
    )
    op.add_column(
        'unidades',
        sa.Column(
            'moodle_autoeval_cmid', sa.Integer(), nullable=True,
            comment='cmid de la autoevaluación (quiz) de la unidad',
        ),
    )
    op.add_column(
        'unidades',
        sa.Column(
            'moodle_cierre_cmid', sa.Integer(), nullable=True,
            comment='cmid de la actividad de cierre (feedback) de la unidad',
        ),
    )

    # Reconstruye las columnas desde los componentes (el de cada tipo).
    op.execute(
        "UPDATE unidades u SET moodle_tp_cmid = c.moodle_cmid "
        "FROM componentes_unidad c WHERE c.unidad_id = u.id AND c.tipo = 'TP'"
    )
    op.execute(
        "UPDATE unidades u SET moodle_autoeval_cmid = c.moodle_cmid "
        "FROM componentes_unidad c WHERE c.unidad_id = u.id AND c.tipo = 'AUTOEVALUACION'"
    )
    op.execute(
        "UPDATE unidades u SET moodle_cierre_cmid = c.moodle_cmid "
        "FROM componentes_unidad c WHERE c.unidad_id = u.id AND c.tipo = 'CIERRE'"
    )

    op.drop_index(op.f('ix_componentes_unidad_unidad_id'), table_name='componentes_unidad')
    op.drop_index(op.f('ix_componentes_unidad_id'), table_name='componentes_unidad')
    op.drop_table('componentes_unidad')

    bind = op.get_bind()
    sa.Enum(name='fuentecomponenteenum').drop(bind, checkfirst=True)
    sa.Enum(name='tipocomponenteenum').drop(bind, checkfirst=True)
