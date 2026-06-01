"""Add Moodle bidireccional fields (Fase 1)

Revision ID: 010_moodle_bidireccional
Revises: 4a01eb61e749
Create Date: 2026-05-29

Fase 1 del plan de integración bidireccional Moodle + toggle key paga:
- entregas.moodle_user_id  : ID del alumno en Moodle (poblado al importar; necesario
                             para publicar nota/feedback con mod_assign_save_grade).
- usuarios.gemini_api_key_paga : toggle manual "mi key tiene billing" (habilita
                             corrección masiva global). NO se infiere por API.
- tabla moodle_sync        : auditoría + idempotencia del envío de correcciones a Moodle.

Todas las columnas nuevas son nullable o tienen server_default → sin backfill,
sin breaking changes en endpoints existentes.

Ref: PLAN_FEAT.md secciones 3.1, 3.2, 3.4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010_moodle_bidireccional'
down_revision: Union[str, None] = '4a01eb61e749'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.fetchone() is not None


def upgrade() -> None:
    conn = op.get_bind()

    # 1) entregas.moodle_user_id (nullable)
    if not _column_exists(conn, 'entregas', 'moodle_user_id'):
        op.add_column(
            'entregas',
            sa.Column('moodle_user_id', sa.Integer(), nullable=True),
        )

    # 2) usuarios.gemini_api_key_paga (NOT NULL con server_default false → seguro para filas existentes)
    if not _column_exists(conn, 'usuarios', 'gemini_api_key_paga'):
        op.add_column(
            'usuarios',
            sa.Column(
                'gemini_api_key_paga',
                sa.Boolean(),
                nullable=False,
                server_default=sa.text('false'),
            ),
        )

    # 3) Enum moodlesyncestado (idempotente)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'moodlesyncestado') THEN
                CREATE TYPE moodlesyncestado AS ENUM ('PENDIENTE', 'ENVIADO', 'ERROR');
            END IF;
        END$$;
    """)

    # 4) Tabla moodle_sync (constraints nombrados según la naming convention del proyecto)
    op.execute("""
        CREATE TABLE IF NOT EXISTS moodle_sync (
            id SERIAL PRIMARY KEY,
            correccion_id INTEGER NOT NULL,
            estado moodlesyncestado NOT NULL,
            nota_enviada VARCHAR(50),
            comentario_enviado TEXT,
            moodle_assignment_id INTEGER,
            moodle_user_id INTEGER,
            mensaje_error TEXT,
            intento INTEGER NOT NULL DEFAULT 1,
            enviado_por_id INTEGER,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now(),
            CONSTRAINT fk_moodle_sync_correccion_id_correcciones
                FOREIGN KEY (correccion_id) REFERENCES correcciones(id),
            CONSTRAINT fk_moodle_sync_enviado_por_id_usuarios
                FOREIGN KEY (enviado_por_id) REFERENCES usuarios(id) ON DELETE SET NULL
        );
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_moodle_sync_id ON moodle_sync(id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_moodle_sync_correccion_id ON moodle_sync(correccion_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_moodle_sync_estado ON moodle_sync(estado);")


def downgrade() -> None:
    # Tabla + índices
    op.execute("DROP TABLE IF EXISTS moodle_sync CASCADE;")
    op.execute("DROP TYPE IF EXISTS moodlesyncestado CASCADE;")

    # Columnas
    conn = op.get_bind()
    if _column_exists(conn, 'usuarios', 'gemini_api_key_paga'):
        op.drop_column('usuarios', 'gemini_api_key_paga')
    if _column_exists(conn, 'entregas', 'moodle_user_id'):
        op.drop_column('entregas', 'moodle_user_id')
