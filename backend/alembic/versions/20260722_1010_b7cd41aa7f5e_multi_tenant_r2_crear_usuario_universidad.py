"""multi-tenant R2: crear tabla usuario_universidad

Revision ID: b7cd41aa7f5e
Revises: f584cac9a6f7
Create Date: 2026-07-22 10:10:00.000000

Fase 0 del feature multi-tenant (openspec/changes/multi-tenant-modelo-datos).
R2 de 7: crea la tabla `usuario_universidad` (membresía usuario<->universidad,
patrón ComisionTutor/CoordinadorMateria + rol scopeado y credenciales Moodle
por membresía). El tipo PG `rol_enum` YA EXISTE (lo creó `usuarios.rol` en la
migración inicial) — se referencia con `create_type=False` para NO recrearlo
(mismo patrón que `componentes_unidad.modo_aprobacion` con
`modoaprobacionenum`, ver 20260607_1829_d6352d492298). Escrita a mano.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7cd41aa7f5e'
down_revision: Union[str, None] = 'f584cac9a6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'usuario_universidad',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=False),
        sa.Column('universidad_id', sa.Integer(), nullable=False),
        sa.Column(
            'rol',
            postgresql.ENUM(name='rol_enum', create_type=False),
            nullable=False,
        ),
        sa.Column('moodle_username', sa.String(length=100), nullable=True),
        sa.Column('moodle_password_encrypted', sa.Text(), nullable=True),
        sa.Column(
            'activo', sa.Boolean(), nullable=False, server_default=sa.text('true'),
        ),
        sa.ForeignKeyConstraint(
            ['usuario_id'], ['usuarios.id'],
            name=op.f('fk_usuario_universidad_usuario_id_usuarios'),
        ),
        sa.ForeignKeyConstraint(
            ['universidad_id'], ['universidades.id'],
            name=op.f('fk_usuario_universidad_universidad_id_universidades'),
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_usuario_universidad')),
        sa.UniqueConstraint(
            'usuario_id', 'universidad_id', name='uq_usuario_universidad',
        ),
    )
    op.create_index(
        op.f('ix_usuario_universidad_id'), 'usuario_universidad', ['id'], unique=False,
    )
    op.create_index(
        op.f('ix_usuario_universidad_usuario_id'),
        'usuario_universidad', ['usuario_id'], unique=False,
    )
    op.create_index(
        op.f('ix_usuario_universidad_universidad_id'),
        'usuario_universidad', ['universidad_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f('ix_usuario_universidad_universidad_id'), table_name='usuario_universidad',
    )
    op.drop_index(
        op.f('ix_usuario_universidad_usuario_id'), table_name='usuario_universidad',
    )
    op.drop_index(op.f('ix_usuario_universidad_id'), table_name='usuario_universidad')
    op.drop_table('usuario_universidad')
    # NO se dropea el tipo rol_enum: create_type=False significa que esta
    # migración no es dueña del tipo (lo sigue usando usuarios.rol).
