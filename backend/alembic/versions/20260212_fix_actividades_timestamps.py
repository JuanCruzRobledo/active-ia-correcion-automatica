"""Fix actividades timestamps to use timezone

Revision ID: 004_fix_actividades_timestamps
Revises: 003_add_actividades
Create Date: 2026-02-12

Alters the created_at and updated_at columns in actividades table
to use TIMESTAMP WITH TIME ZONE (TIMESTAMPTZ) to properly handle
timezone-aware timestamps and fix the 3-hour offset issue.

Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '004_fix_actividades_timestamps'
down_revision: Union[str, None] = '003_add_actividades'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Alter created_at to use TIMESTAMPTZ with server default
    op.execute("""
        ALTER TABLE actividades
        ALTER COLUMN created_at TYPE TIMESTAMP WITH TIME ZONE
        USING created_at AT TIME ZONE 'UTC';
    """)

    # Alter updated_at to use TIMESTAMPTZ with server default
    op.execute("""
        ALTER TABLE actividades
        ALTER COLUMN updated_at TYPE TIMESTAMP WITH TIME ZONE
        USING updated_at AT TIME ZONE 'UTC';
    """)


def downgrade() -> None:
    # Revert created_at back to TIMESTAMP without timezone
    op.execute("""
        ALTER TABLE actividades
        ALTER COLUMN created_at TYPE TIMESTAMP WITHOUT TIME ZONE;
    """)

    # Revert updated_at back to TIMESTAMP without timezone
    op.execute("""
        ALTER TABLE actividades
        ALTER COLUMN updated_at TYPE TIMESTAMP WITHOUT TIME ZONE;
    """)
