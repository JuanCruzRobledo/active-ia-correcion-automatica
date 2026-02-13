"""Add actividades table for audit log

Revision ID: 003_add_actividades
Revises: 002_remove_activo_entregas
Create Date: 2026-02-12

Creates the actividades table to track important system actions:
- User creation (Admin, Coordinador, Tutor)
- Materia creation
- Comision creation
- Rubrica creation

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003_add_actividades'
down_revision: Union[str, None] = '002_remove_activo_entregas'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tipo_actividad_enum using raw SQL (skip if already exists)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tipoactividadenum') THEN
                CREATE TYPE tipoactividadenum AS ENUM ('USUARIO_CREADO', 'MATERIA_CREADA', 'COMISION_CREADA', 'RUBRICA_CREADA');
            END IF;
        END$$;
    """)

    # Create actividades table using raw SQL
    op.execute("""
        CREATE TABLE IF NOT EXISTS actividades (
            id SERIAL PRIMARY KEY,
            tipo tipoactividadenum NOT NULL,
            usuario_id INTEGER,
            descripcion VARCHAR(500) NOT NULL,
            entidad_id INTEGER NOT NULL,
            entidad_nombre VARCHAR(255) NOT NULL,
            metadatos TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT fk_actividades_usuario_id_usuarios
                FOREIGN KEY (usuario_id)
                REFERENCES usuarios(id)
                ON DELETE SET NULL
        );
    """)

    # Create indexes using raw SQL
    op.execute("CREATE INDEX IF NOT EXISTS ix_actividades_tipo ON actividades(tipo);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_actividades_created_at ON actividades(created_at);")



def downgrade() -> None:
    # Drop table (indexes will be dropped automatically)
    op.execute("DROP TABLE IF EXISTS actividades CASCADE;")

    # Drop enum
    op.execute("DROP TYPE IF EXISTS tipoactividadenum CASCADE;")
