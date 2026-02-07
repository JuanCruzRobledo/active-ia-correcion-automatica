"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-26

Creates all tables for Active-IA system:
- usuarios (with roles: ADMIN, COORDINADOR, TUTOR)
- materias
- coordinador_materia (N:M relation)
- comisiones
- comision_tutor (N:M relation)
- rubricas
- entregas (with partial unique index)
- entregas_historial
- correcciones

Also creates PostgreSQL ENUM types.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create ENUM types
    op.execute("CREATE TYPE rol_enum AS ENUM ('ADMIN', 'COORDINADOR', 'TUTOR')")
    op.execute("CREATE TYPE tipo_rubrica_enum AS ENUM ('TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL')")
    op.execute("CREATE TYPE estado_entrega_enum AS ENUM ('SUBIDA', 'PENDIENTE', 'CORREGIDA', 'ERROR')")
    op.execute("CREATE TYPE fuente_rubrica_enum AS ENUM ('manual', 'pdf')")
    
    # Create usuarios table
    op.create_table(
        'usuarios',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('rol', postgresql.ENUM('ADMIN', 'COORDINADOR', 'TUTOR', name='rol_enum', create_type=False), nullable=False),
        sa.Column('gemini_api_key_encrypted', sa.Text(), nullable=True),
        sa.Column('gemini_api_key_valid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('primer_login', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_usuarios')),
        sa.UniqueConstraint('username', name=op.f('uq_usuarios_username'))
    )
    op.create_index(op.f('ix_usuarios_id'), 'usuarios', ['id'], unique=False)
    op.create_index(op.f('ix_usuarios_username'), 'usuarios', ['username'], unique=True)
    op.create_index(op.f('ix_usuarios_rol'), 'usuarios', ['rol'], unique=False)
    op.create_index(op.f('ix_usuarios_activo'), 'usuarios', ['activo'], unique=False)
    
    # Create materias table
    op.create_table(
        'materias',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=20), nullable=False),
        sa.Column('nombre', sa.String(length=100), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_materias')),
        sa.UniqueConstraint('codigo', name=op.f('uq_materias_codigo'))
    )
    op.create_index(op.f('ix_materias_id'), 'materias', ['id'], unique=False)
    op.create_index(op.f('ix_materias_codigo'), 'materias', ['codigo'], unique=True)
    op.create_index(op.f('ix_materias_activa'), 'materias', ['activa'], unique=False)
    
    # Create coordinador_materia table (N:M)
    op.create_table(
        'coordinador_materia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('coordinador_id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('asignado_en', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['coordinador_id'], ['usuarios.id'], name=op.f('fk_coordinador_materia_coordinador_id_usuarios')),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'], name=op.f('fk_coordinador_materia_materia_id_materias')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_coordinador_materia')),
        sa.UniqueConstraint('coordinador_id', 'materia_id', name='uq_coordinador_materia')
    )
    op.create_index(op.f('ix_coordinador_materia_id'), 'coordinador_materia', ['id'], unique=False)
    
    # Create comisiones table
    op.create_table(
        'comisiones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=50), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'], name=op.f('fk_comisiones_materia_id_materias')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_comisiones')),
        sa.UniqueConstraint('materia_id', 'nombre', 'anio', name='uq_comision_materia_nombre_anio')
    )
    op.create_index(op.f('ix_comisiones_id'), 'comisiones', ['id'], unique=False)
    op.create_index(op.f('ix_comisiones_materia_id'), 'comisiones', ['materia_id'], unique=False)
    op.create_index(op.f('ix_comisiones_anio'), 'comisiones', ['anio'], unique=False)
    op.create_index(op.f('ix_comisiones_activa'), 'comisiones', ['activa'], unique=False)
    
    # Create comision_tutor table (N:M)
    op.create_table(
        'comision_tutor',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comision_id', sa.Integer(), nullable=False),
        sa.Column('tutor_id', sa.Integer(), nullable=False),
        sa.Column('asignado_en', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['comision_id'], ['comisiones.id'], name=op.f('fk_comision_tutor_comision_id_comisiones')),
        sa.ForeignKeyConstraint(['tutor_id'], ['usuarios.id'], name=op.f('fk_comision_tutor_tutor_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_comision_tutor')),
        sa.UniqueConstraint('comision_id', 'tutor_id', name='uq_comision_tutor')
    )
    op.create_index(op.f('ix_comision_tutor_id'), 'comision_tutor', ['id'], unique=False)
    
    # Create rubricas table (V2 schema)
    op.create_table(
        'rubricas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('materia_id', sa.Integer(), nullable=False),
        sa.Column('tipo', postgresql.ENUM('TP', 'PARCIAL_1', 'PARCIAL_2', 'RECUPERATORIO_1', 'RECUPERATORIO_2', 'FINAL', 'GLOBAL', name='tipo_rubrica_enum', create_type=False), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('anio', sa.Integer(), nullable=False),
        # V2 fields
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=False),
        sa.Column('puntaje_maximo', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('criterios_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('penalizaciones_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('condiciones_desaprobacion_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        # Control fields
        sa.Column('fuente', postgresql.ENUM('manual', 'pdf', name='fuente_rubrica_enum', create_type=False), nullable=False, server_default='manual'),
        sa.Column('archivo_original', sa.String(length=255), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['materia_id'], ['materias.id'], name=op.f('fk_rubricas_materia_id_materias')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_rubricas')),
        sa.UniqueConstraint('materia_id', 'tipo', 'numero', 'anio', name='uq_rubrica_materia_tipo_numero_anio')
    )
    op.create_index(op.f('ix_rubricas_id'), 'rubricas', ['id'], unique=False)
    op.create_index(op.f('ix_rubricas_materia_id'), 'rubricas', ['materia_id'], unique=False)
    op.create_index(op.f('ix_rubricas_anio'), 'rubricas', ['anio'], unique=False)
    op.create_index(op.f('ix_rubricas_titulo'), 'rubricas', ['titulo'], unique=False)
    op.create_index(op.f('ix_rubricas_activa'), 'rubricas', ['activa'], unique=False)
    
    # Create entregas table
    op.create_table(
        'entregas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comision_id', sa.Integer(), nullable=False),
        sa.Column('rubrica_id', sa.Integer(), nullable=False),
        sa.Column('alumno_nombre', sa.String(length=100), nullable=False),
        sa.Column('archivo_nombre', sa.String(length=255), nullable=False),
        sa.Column('archivo_ruta', sa.String(length=500), nullable=False),
        sa.Column('archivo_tamanio', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('archivo_tipo', sa.String(length=10), nullable=False),
        sa.Column('contenido_preview', sa.Text(), nullable=True),
        sa.Column('estado', postgresql.ENUM('SUBIDA', 'PENDIENTE', 'CORREGIDA', 'ERROR', name='estado_entrega_enum', create_type=False), nullable=False, server_default='SUBIDA'),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('subido_por_id', sa.Integer(), nullable=False),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comision_id'], ['comisiones.id'], name=op.f('fk_entregas_comision_id_comisiones')),
        sa.ForeignKeyConstraint(['rubrica_id'], ['rubricas.id'], name=op.f('fk_entregas_rubrica_id_rubricas')),
        sa.ForeignKeyConstraint(['subido_por_id'], ['usuarios.id'], name=op.f('fk_entregas_subido_por_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_entregas'))
    )
    op.create_index(op.f('ix_entregas_id'), 'entregas', ['id'], unique=False)
    op.create_index(op.f('ix_entregas_comision_id'), 'entregas', ['comision_id'], unique=False)
    op.create_index(op.f('ix_entregas_rubrica_id'), 'entregas', ['rubrica_id'], unique=False)
    op.create_index(op.f('ix_entregas_estado'), 'entregas', ['estado'], unique=False)
    op.create_index(op.f('ix_entregas_hash_sha256'), 'entregas', ['hash_sha256'], unique=False)
    op.create_index(op.f('ix_entregas_activo'), 'entregas', ['activo'], unique=False)
    # Partial unique index: only active entregas
    op.create_index(
        'uq_entrega_rubrica_alumno_activo',
        'entregas',
        ['rubrica_id', 'alumno_nombre'],
        unique=True,
        postgresql_where=sa.text('activo = true')
    )
    
    # Create entregas_historial table
    op.create_table(
        'entregas_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entrega_actual_id', sa.Integer(), nullable=False),
        sa.Column('alumno_nombre', sa.String(length=100), nullable=False),
        sa.Column('archivo_nombre', sa.String(length=255), nullable=False),
        sa.Column('archivo_ruta', sa.String(length=500), nullable=False),
        sa.Column('archivo_tamanio', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('contenido_preview', sa.Text(), nullable=True),
        sa.Column('hash_sha256', sa.String(length=64), nullable=True),
        sa.Column('nota_anterior', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('correccion_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('sobrescrito_en', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('sobrescrito_por_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['entrega_actual_id'], ['entregas.id'], name=op.f('fk_entregas_historial_entrega_actual_id_entregas')),
        sa.ForeignKeyConstraint(['sobrescrito_por_id'], ['usuarios.id'], name=op.f('fk_entregas_historial_sobrescrito_por_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_entregas_historial'))
    )
    op.create_index(op.f('ix_entregas_historial_id'), 'entregas_historial', ['id'], unique=False)
    op.create_index(op.f('ix_entregas_historial_entrega_actual_id'), 'entregas_historial', ['entrega_actual_id'], unique=False)
    
    # Create correcciones table
    op.create_table(
        'correcciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('entrega_id', sa.Integer(), nullable=False),
        sa.Column('nota', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('criterios_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('fortalezas', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('recomendaciones', postgresql.ARRAY(sa.Text()), nullable=False, server_default='{}'),
        sa.Column('comentario_general', sa.Text(), nullable=True),
        sa.Column('editado_manualmente', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('corregido_por_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['entrega_id'], ['entregas.id'], name=op.f('fk_correcciones_entrega_id_entregas')),
        sa.ForeignKeyConstraint(['corregido_por_id'], ['usuarios.id'], name=op.f('fk_correcciones_corregido_por_id_usuarios')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_correcciones')),
        sa.UniqueConstraint('entrega_id', name=op.f('uq_correcciones_entrega_id'))
    )
    op.create_index(op.f('ix_correcciones_id'), 'correcciones', ['id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_correcciones_id'), table_name='correcciones')
    op.drop_table('correcciones')
    
    op.drop_index(op.f('ix_entregas_historial_entrega_actual_id'), table_name='entregas_historial')
    op.drop_index(op.f('ix_entregas_historial_id'), table_name='entregas_historial')
    op.drop_table('entregas_historial')
    
    op.drop_index('uq_entrega_rubrica_alumno_activo', table_name='entregas')
    op.drop_index(op.f('ix_entregas_activo'), table_name='entregas')
    op.drop_index(op.f('ix_entregas_hash_sha256'), table_name='entregas')
    op.drop_index(op.f('ix_entregas_estado'), table_name='entregas')
    op.drop_index(op.f('ix_entregas_rubrica_id'), table_name='entregas')
    op.drop_index(op.f('ix_entregas_comision_id'), table_name='entregas')
    op.drop_index(op.f('ix_entregas_id'), table_name='entregas')
    op.drop_table('entregas')
    
    op.drop_index(op.f('ix_rubricas_activa'), table_name='rubricas')
    op.drop_index(op.f('ix_rubricas_titulo'), table_name='rubricas')
    op.drop_index(op.f('ix_rubricas_anio'), table_name='rubricas')
    op.drop_index(op.f('ix_rubricas_materia_id'), table_name='rubricas')
    op.drop_index(op.f('ix_rubricas_id'), table_name='rubricas')
    op.drop_table('rubricas')
    
    op.drop_index(op.f('ix_comision_tutor_id'), table_name='comision_tutor')
    op.drop_table('comision_tutor')
    
    op.drop_index(op.f('ix_comisiones_activa'), table_name='comisiones')
    op.drop_index(op.f('ix_comisiones_anio'), table_name='comisiones')
    op.drop_index(op.f('ix_comisiones_materia_id'), table_name='comisiones')
    op.drop_index(op.f('ix_comisiones_id'), table_name='comisiones')
    op.drop_table('comisiones')
    
    op.drop_index(op.f('ix_coordinador_materia_id'), table_name='coordinador_materia')
    op.drop_table('coordinador_materia')
    
    op.drop_index(op.f('ix_materias_activa'), table_name='materias')
    op.drop_index(op.f('ix_materias_codigo'), table_name='materias')
    op.drop_index(op.f('ix_materias_id'), table_name='materias')
    op.drop_table('materias')
    
    op.drop_index(op.f('ix_usuarios_activo'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_rol'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_username'), table_name='usuarios')
    op.drop_index(op.f('ix_usuarios_id'), table_name='usuarios')
    op.drop_table('usuarios')
    
    # Drop ENUM types
    op.execute('DROP TYPE fuente_rubrica_enum')
    op.execute('DROP TYPE estado_entrega_enum')
    op.execute('DROP TYPE tipo_rubrica_enum')
    op.execute('DROP TYPE rol_enum')
