"""trabajos practicos y ejercicios con external_ref

Revision ID: 56a1724602e2
Revises: e7a3c9d1b502
Create Date: 2026-08-20

Change: `trabajos-practicos-y-external-ref`.

Habilita corregir un TP **ejercicio por ejercicio**, que es lo que AI-Native
necesita y lo que desactiva el modo de fallo del motor donde una pieza del
ejercicio 3 cuenta como cumplimiento de un criterio del 1.

Cinco pasos:

1. `trabajos_practicos` — agrupa N ejercicios bajo una materia.
2. `ejercicios` — la unidad de corrección, con su enunciado, peso y test_cases.
3. `materias.external_ref` — identificador del sistema cliente, opcional.
4. `rubricas.ejercicio_id` — el 1:1 entre ejercicio y rúbrica.
5. `uq_rubrica_materia_tipo_numero_anio` pasa de UNIQUE CONSTRAINT total a
   ÍNDICE ÚNICO PARCIAL sobre `ejercicio_id IS NULL`.

**El paso 5 es el único no aditivo.** Y es seguro sobre los datos existentes,
por una razón concreta: `ejercicio_id` es una columna que se crea en esta misma
migración, así que TODAS las filas preexistentes quedan con `ejercicio_id NULL`.
El índice parcial cubre exactamente el mismo conjunto de filas que el constraint
total que reemplaza — no puede fallar por datos previos. Las rúbricas del flujo
de Moodle conservan idéntica unicidad.

Sin el paso 5, los cuatro ejercicios de un TP no pueden tener cuatro rúbricas:
las cuatro comparten `(materia_id, tipo, numero, anio)` y el constraint total
rechaza de la segunda en adelante.

NOTA SOBRE EL DOWNGRADE. Vuelve al UNIQUE CONSTRAINT total. Si al momento de
bajar ya existen rúbricas de ejercicio (varias con la misma clave y distinto
`ejercicio_id`), la creación del constraint VA A FALLAR. Es esperable y
correcto: bajar exige resolver esas filas a mano antes. Mismo criterio que la
migración e7a3c9d1b502 (CRUD-011).

NOTA SOBRE EL AUTOGENERATE. `--autogenerate` detectó, además de estos cinco
pasos, drift preexistente entre los modelos y la base (comments de columnas,
server defaults, `ix_materias_codigo`, el FK de `moodle_sync` y el único
`uq_universidades_nombre`). **Nada de eso entra acá**: dos de esas operaciones
cambiarían comportamiento fuera del alcance de este change — el FK de
`moodle_sync` se recreaba SIN su `ondelete='SET NULL'`, y `uq_universidades_nombre`
se eliminaba. Ese drift es un hallazgo aparte y merece su propio change.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '56a1724602e2'
down_revision: Union[str, None] = 'e7a3c9d1b502'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- 1. trabajos_practicos -------------------------------------------------
    op.create_table(
        'trabajos_practicos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('universidad_id', sa.Integer(), nullable=False),
        sa.Column('external_ref', sa.String(length=64), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['materia_id'], ['materias.id'],
            name=op.f('fk_trabajos_practicos_materia_id_materias'),
        ),
        sa.ForeignKeyConstraint(
            ['universidad_id'], ['universidades.id'],
            name=op.f('fk_trabajos_practicos_universidad_id_universidades'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_trabajos_practicos')),
    )
    op.create_index(op.f('ix_trabajos_practicos_id'), 'trabajos_practicos', ['id'])
    op.create_index(
        op.f('ix_trabajos_practicos_materia_id'), 'trabajos_practicos', ['materia_id']
    )
    op.create_index(
        op.f('ix_trabajos_practicos_universidad_id'),
        'trabajos_practicos', ['universidad_id'],
    )
    # Parcial sobre no borrados: un TP dado de baja no debe bloquear la
    # republicación de otro con el mismo identificador externo.
    op.create_index(
        'uq_trabajo_practico_materia_external_ref',
        'trabajos_practicos',
        ['materia_id', 'external_ref'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    # --- 2. ejercicios ---------------------------------------------------------
    op.create_table(
        'ejercicios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('trabajo_practico_id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('universidad_id', sa.Integer(), nullable=False),
        sa.Column('external_ref', sa.String(length=64), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('enunciado_md', sa.Text(), nullable=True),
        sa.Column(
            'peso',
            sa.Numeric(precision=5, scale=2),
            server_default=sa.text('1.00'),
            nullable=False,
            comment='Peso relativo dentro del TP. Metadata: Active-IA no calcula la nota del TP.',
        ),
        sa.Column(
            'test_cases',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
            comment=(
                'Casos de prueba como parte del enunciado. NO se ejecutan. '
                'Los casos no públicos no conservan salida_esperada ni asercion.'
            ),
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ['materia_id'], ['materias.id'], name=op.f('fk_ejercicios_materia_id_materias')
        ),
        sa.ForeignKeyConstraint(
            ['trabajo_practico_id'], ['trabajos_practicos.id'],
            name=op.f('fk_ejercicios_trabajo_practico_id_trabajos_practicos'),
        ),
        sa.ForeignKeyConstraint(
            ['universidad_id'], ['universidades.id'],
            name=op.f('fk_ejercicios_universidad_id_universidades'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ejercicios')),
    )
    op.create_index(op.f('ix_ejercicios_id'), 'ejercicios', ['id'])
    op.create_index(op.f('ix_ejercicios_materia_id'), 'ejercicios', ['materia_id'])
    op.create_index(
        op.f('ix_ejercicios_trabajo_practico_id'), 'ejercicios', ['trabajo_practico_id']
    )
    op.create_index(
        op.f('ix_ejercicios_universidad_id'), 'ejercicios', ['universidad_id']
    )
    op.create_index(
        'uq_ejercicio_materia_external_ref',
        'ejercicios',
        ['materia_id', 'external_ref'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL'),
    )

    # --- 3. materias.external_ref ---------------------------------------------
    op.add_column('materias', sa.Column('external_ref', sa.String(length=64), nullable=True))
    # Parcial sobre no nulos: la enorme mayoría de las materias (las de Moodle)
    # no tienen identificador externo, y varios NULL no deben colisionar.
    op.create_index(
        'uq_materia_universidad_external_ref',
        'materias',
        ['universidad_id', 'external_ref'],
        unique=True,
        postgresql_where=sa.text('external_ref IS NOT NULL'),
    )

    # --- 4. rubricas.ejercicio_id (1:1 con ejercicio) --------------------------
    op.add_column('rubricas', sa.Column('ejercicio_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_rubricas_ejercicio_id'), 'rubricas', ['ejercicio_id'], unique=True
    )
    op.create_foreign_key(
        op.f('fk_rubricas_ejercicio_id_ejercicios'),
        'rubricas', 'ejercicios', ['ejercicio_id'], ['id'],
    )

    # --- 5. el único de rúbricas pasa a ser PARCIAL ----------------------------
    # Seguro sobre datos existentes: `ejercicio_id` acaba de crearse, así que
    # todas las filas previas tienen NULL y el índice parcial cubre exactamente
    # el mismo conjunto que el constraint total que reemplaza.
    op.drop_constraint(
        op.f('uq_rubrica_materia_tipo_numero_anio'), 'rubricas', type_='unique'
    )
    op.create_index(
        'uq_rubrica_materia_tipo_numero_anio',
        'rubricas',
        ['materia_id', 'tipo', 'numero', 'anio'],
        unique=True,
        postgresql_where=sa.text('ejercicio_id IS NULL'),
    )


def downgrade() -> None:
    # Orden inverso. Ver la NOTA SOBRE EL DOWNGRADE del encabezado: si ya existen
    # rúbricas de ejercicio, el paso 5 invertido falla a propósito.
    op.drop_index('uq_rubrica_materia_tipo_numero_anio', table_name='rubricas')
    op.create_unique_constraint(
        op.f('uq_rubrica_materia_tipo_numero_anio'),
        'rubricas',
        ['materia_id', 'tipo', 'numero', 'anio'],
    )

    op.drop_constraint(
        op.f('fk_rubricas_ejercicio_id_ejercicios'), 'rubricas', type_='foreignkey'
    )
    op.drop_index(op.f('ix_rubricas_ejercicio_id'), table_name='rubricas')
    op.drop_column('rubricas', 'ejercicio_id')

    op.drop_index('uq_materia_universidad_external_ref', table_name='materias')
    op.drop_column('materias', 'external_ref')

    op.drop_index('uq_ejercicio_materia_external_ref', table_name='ejercicios')
    op.drop_index(op.f('ix_ejercicios_universidad_id'), table_name='ejercicios')
    op.drop_index(op.f('ix_ejercicios_trabajo_practico_id'), table_name='ejercicios')
    op.drop_index(op.f('ix_ejercicios_materia_id'), table_name='ejercicios')
    op.drop_index(op.f('ix_ejercicios_id'), table_name='ejercicios')
    op.drop_table('ejercicios')

    op.drop_index(
        'uq_trabajo_practico_materia_external_ref', table_name='trabajos_practicos'
    )
    op.drop_index(
        op.f('ix_trabajos_practicos_universidad_id'), table_name='trabajos_practicos'
    )
    op.drop_index(
        op.f('ix_trabajos_practicos_materia_id'), table_name='trabajos_practicos'
    )
    op.drop_index(op.f('ix_trabajos_practicos_id'), table_name='trabajos_practicos')
    op.drop_table('trabajos_practicos')
