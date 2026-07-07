"""cierre de cursada: dirigido por examenes (drop mapeo manual)

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-07-05 10:00:00.000000

El cierre de cursada deja de depender del mapeo manual de items del
calificador (`cierre_cursada_items` / `CategoriaItemCierreEnum`) y pasa a
derivar el veredicto y la Nota Final EXCLUSIVAMENTE de `ExamenMateria`
(PARCIAL/GLOBAL, `nota_minima`, cadenas de rescate) — ver
`.kiro/specs/cierre-cursada-fix/design.md`, seccion "Destino de
CierreCursadaItem".

Cambios:
- DROP de `cierre_cursada_items` (+ su tipo enum nativo
  `categoriaitemcierreenum`; no hay ninguna otra referencia a
  `CategoriaItemCierreEnum`/`categoriaitemcierreenum` en el resto del
  codigo Python — verificado por busqueda — asi que es seguro dropear
  tambien el tipo).
- `cierre_cursada_runs`: `umbral_tp_pct` y `reglas_snapshot` pasan a ser
  NULLABLE (legacy, dejan de escribirse); se agrega `examenes_snapshot`
  (JSONB nullable) para congelar la config de examenes de la corrida.
- `cierre_cursada_alumnos`: las columnas del shape fijo viejo (`tp_ok`,
  `autoeval_ok`, `p1_max`, `p2_max`, `tpi_max`, `parcial1_instancias`,
  `parcial2_instancias`, `tpi_instancias`, `habilitado_final`) pasan a ser
  NULLABLE (legacy, dejan de escribirse); se agregan `resultados_examenes`
  (JSONB nullable) y `global_valor` (Float nullable). NO se agrega ninguna
  columna de TPs (el modelo corregido no las tiene y `ExamenMateria` no
  modela TPs).

Las corridas historicas (generadas antes de este fix) quedan legibles: sus
columnas legacy conservan los datos ya escritos. Su Excel, si se
regenerase, usaria el layout nuevo (best-effort — no reproduce 1:1 el shape
viejo, ya documentado como aceptable en el diseno).

Escrita a mano (no hay conexion a una BD Postgres real disponible para
`alembic revision --autogenerate` en el entorno de generacion de este
archivo), mismo estilo que `20260704_1000_c2d3e4f5a6b7_cierre_cursada.py`
(sa.Enum inline, op.f() para constraint names, JSONB de
postgresql.dialects, DROP TYPE explicito).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e4f5a6b7c8d9'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. Mapeo manual de items -> eliminado (ExamenMateria ya trae moodle_cmid). ---
    op.drop_index(op.f('ix_cierre_cursada_items_cuatrimestre_id'), table_name='cierre_cursada_items')
    op.drop_index(op.f('ix_cierre_cursada_items_materia_id'), table_name='cierre_cursada_items')
    op.drop_index(op.f('ix_cierre_cursada_items_id'), table_name='cierre_cursada_items')
    op.drop_table('cierre_cursada_items')
    # El tipo enum nativo de PG no se elimina al dropear la tabla -> limpiarlo.
    # Sin otras referencias a CategoriaItemCierreEnum/categoriaitemcierreenum en el
    # resto del codigo Python -> seguro dropear tambien el tipo (no sólo la tabla).
    op.execute("DROP TYPE IF EXISTS categoriaitemcierreenum")

    # --- 2. cierre_cursada_runs: deprecar umbral/reglas fijas, agregar snapshot de examenes. ---
    op.alter_column('cierre_cursada_runs', 'umbral_tp_pct',
                     existing_type=sa.Float(), nullable=True)
    op.alter_column('cierre_cursada_runs', 'reglas_snapshot',
                     existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.add_column(
        'cierre_cursada_runs',
        sa.Column(
            'examenes_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
            comment='Config de ExamenMateria (PARCIAL/GLOBAL) CONGELADA al momento de la '
            'corrida — reproducibilidad historica del cierre dirigido por examen',
        ),
    )

    # --- 3. cierre_cursada_alumnos: deprecar shape fijo viejo, agregar campos dirigidos por examen. ---
    op.alter_column('cierre_cursada_alumnos', 'tp_ok',
                     existing_type=sa.Boolean(), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'autoeval_ok',
                     existing_type=sa.Boolean(), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'p1_max',
                     existing_type=sa.Float(), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'p2_max',
                     existing_type=sa.Float(), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'tpi_max',
                     existing_type=sa.Float(), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'parcial1_instancias',
                     existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'parcial2_instancias',
                     existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'tpi_instancias',
                     existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    op.alter_column('cierre_cursada_alumnos', 'habilitado_final',
                     existing_type=sa.String(length=60), nullable=True)
    op.add_column(
        'cierre_cursada_alumnos',
        sa.Column(
            'resultados_examenes', postgresql.JSONB(astext_type=sa.Text()), nullable=True,
            comment='Lista por examen principal: [{examen_id, etiqueta, tipo, modo, '
            'valor_real, resultado_escala, cumple_minimo, cumple_banda, rescatado}] '
            '— auditoria dirigida por config',
        ),
    )
    op.add_column(
        'cierre_cursada_alumnos',
        sa.Column(
            'global_valor', sa.Float(), nullable=True,
            comment="Nota del examen GLOBAL con rescate aplicado (columna 'Global TPI' "
            "del Excel); None = 'N/E'",
        ),
    )


def downgrade() -> None:
    # --- 3. cierre_cursada_alumnos: revertir al shape fijo viejo. ---
    op.drop_column('cierre_cursada_alumnos', 'global_valor')
    op.drop_column('cierre_cursada_alumnos', 'resultados_examenes')
    op.alter_column('cierre_cursada_alumnos', 'habilitado_final',
                     existing_type=sa.String(length=60), nullable=False)
    # p1_max / p2_max / tpi_max / parcial{1,2}_instancias / tpi_instancias ya eran
    # nullable=True en c2d3e4f5a6b7 (creacion original) -> no se revierten a NOT NULL.
    op.alter_column('cierre_cursada_alumnos', 'autoeval_ok',
                     existing_type=sa.Boolean(), nullable=False)
    op.alter_column('cierre_cursada_alumnos', 'tp_ok',
                     existing_type=sa.Boolean(), nullable=False)

    # --- 2. cierre_cursada_runs: revertir al shape fijo viejo. ---
    op.drop_column('cierre_cursada_runs', 'examenes_snapshot')
    op.alter_column('cierre_cursada_runs', 'reglas_snapshot',
                     existing_type=postgresql.JSONB(astext_type=sa.Text()), nullable=False)
    op.alter_column('cierre_cursada_runs', 'umbral_tp_pct',
                     existing_type=sa.Float(), nullable=False)

    # --- 1. Recrear cierre_cursada_items + su tipo enum (mismo shape que c2d3e4f5a6b7). ---
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
