"""
Fase 4 multi-tenant (multi-tenant-scoping-queries, D7 estricto / OQ4): precondición
del filtro ESTRICTO `WHERE universidad_id = :activa` — CERO filas con
`universidad_id IS NULL` en las 9 tablas scopeadas.

Corre contra el Postgres REAL (no el SQLite in-memory de la suite unitaria):
el objetivo es verificar el estado de los datos migrados por Fase 0 (backfill +
migración R7 NOT NULL), no el esquema del modelo (eso ya lo cubre
tests/unit/models/test_universidad_id_denormalizado.py). Si el Postgres de
desarrollo no está disponible, el test se saltea (no es parte del harness
unitario estándar; requiere `docker-compose -f docker-compose.local.yml up -d`).
"""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/active_ia_db",
)

TABLAS_SCOPEADAS = [
    "materias",
    "comisiones",
    "entregas",
    "correcciones",
    "unidades",
    "rubricas",
    "examenes_materia",
    "cierre_cursada_runs",
    "avance_snapshots",
]


async def _engine_disponible():
    try:
        engine = create_async_engine(DATABASE_URL)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:  # noqa: BLE001 — probing de disponibilidad, no un test en sí
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("tabla", TABLAS_SCOPEADAS)
async def test_tabla_no_tiene_filas_con_universidad_id_null(tabla):
    """D7 estricto: cero filas con universidad_id NULL en la DB real (precondición
    del filtro `WHERE universidad_id = :activa`, nunca `OR IS NULL`)."""
    if not await _engine_disponible():
        pytest.skip(
            "Postgres real no disponible (levantar con "
            "docker-compose -f docker-compose.local.yml up -d) — "
            "este test valida el estado de los datos migrados, no el esquema."
        )

    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(f"SELECT COUNT(*) FROM {tabla} WHERE universidad_id IS NULL")
            )
            count = result.scalar_one()
    finally:
        await engine.dispose()

    assert count == 0, (
        f"{tabla} tiene {count} fila(s) con universidad_id NULL — "
        "el filtro estricto (D7-A) las excluiría silenciosamente de TODAS las "
        "universidades. Corregir el backfill antes de confiar en el filtro."
    )


@pytest.mark.asyncio
async def test_las_9_columnas_son_not_null_en_postgres():
    """Confirma que la DB real ya endurece universidad_id a NOT NULL (migración
    R7 de Fase 0) — el modelo SQLAlchemy (Fase 4) se alinea a esto, no al revés."""
    if not await _engine_disponible():
        pytest.skip("Postgres real no disponible.")

    engine = create_async_engine(DATABASE_URL)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT table_name, is_nullable FROM information_schema.columns "
                    "WHERE column_name = 'universidad_id' "
                    "AND table_name = ANY(:tablas)"
                ),
                {"tablas": TABLAS_SCOPEADAS},
            )
            filas = {row.table_name: row.is_nullable for row in result}
    finally:
        await engine.dispose()

    assert set(filas.keys()) == set(TABLAS_SCOPEADAS), (
        f"Faltan tablas: {set(TABLAS_SCOPEADAS) - set(filas.keys())}"
    )
    no_nulleables = {t: n for t, n in filas.items() if n != "NO"}
    assert not no_nulleables, (
        f"Estas tablas todavía permiten NULL en universidad_id: {no_nulleables}"
    )
