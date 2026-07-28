"""
IA-004: entregas colgadas en PENDIENTE para siempre si el proceso muere.

Los lotes corren como BackgroundTasks en el MISMO proceso: no es una cola durable.
Si el contenedor se reinicia a mitad de un lote, las entregas en PENDIENTE quedan
así indefinidamente (no había ningún job que las detectara). Un watchdog al arranque
las pasa a ERROR (código CORRECCION_INTERRUMPIDA), ya que tras un restart cualquier
PENDIENTE quedó huérfano (los BackgroundTasks no sobreviven al restart).
"""

import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.comision import Comision
from app.models.correccion import Correccion
from app.models.entrega import Entrega, EntregaHistorial
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.repositories.entrega_repository import EntregaRepository

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL


sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)


@compiles(JSONB, "sqlite")
def _j(e, c, **k):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _a(e, c, **k):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(
            Base.metadata.create_all,
            tables=[Materia.__table__, Comision.__table__, Rubrica.__table__,
                    Entrega.__table__, EntregaHistorial.__table__, Correccion.__table__],
        )
    maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def _setup(db):
    m = Materia(universidad_id=UNIV_ID, nombre="M", codigo="M"); db.add(m); await db.flush()
    c = Comision(universidad_id=UNIV_ID, materia_id=m.id, nombre="C", anio=2026, activa=True); db.add(c); await db.flush()
    rid = [0]

    def _mk(estado):
        rid[0] += 1
        return Entrega(universidad_id=UNIV_ID, comision_id=c.id, rubrica_id=1, alumno_nombre=f"A{rid[0]}",
                       archivo_nombre="a.py", archivo_tipo="individual", estado=estado)

    db.add_all([
        _mk(EstadoEntregaEnum.PENDIENTE),
        _mk(EstadoEntregaEnum.PENDIENTE),
        _mk(EstadoEntregaEnum.SUBIDA),
        _mk(EstadoEntregaEnum.CORREGIDA),
    ])
    await db.commit()


async def _estados(db):
    """Select directo de columnas (sin selectin de relaciones)."""
    from sqlalchemy import select as _select

    rows = await db.execute(_select(Entrega.estado, Entrega.error_code))
    return list(rows.all())


@pytest.mark.asyncio
async def test_watchdog_pasa_pendientes_a_error(db_session):
    await _setup(db_session)
    repo = EntregaRepository(db_session)

    count = await repo.reset_pendientes_interrumpidas()
    assert count == 2   # solo las 2 PENDIENTE

    filas = await _estados(db_session)
    estados = [e for e, _ in filas]
    assert EstadoEntregaEnum.PENDIENTE not in estados  # ya no hay pendientes
    errores = [(e, code) for e, code in filas if e == EstadoEntregaEnum.ERROR]
    assert len(errores) == 2
    assert all(code == "CORRECCION_INTERRUMPIDA" for _, code in errores)


@pytest.mark.asyncio
async def test_watchdog_no_toca_subida_ni_corregida(db_session):
    await _setup(db_session)
    repo = EntregaRepository(db_session)
    await repo.reset_pendientes_interrumpidas()

    estados = {e for e, _ in await _estados(db_session)}
    assert EstadoEntregaEnum.SUBIDA in estados
    assert EstadoEntregaEnum.CORREGIDA in estados


@pytest.mark.asyncio
async def test_watchdog_sin_pendientes_devuelve_cero(db_session):
    m = Materia(universidad_id=UNIV_ID, nombre="M", codigo="M"); db_session.add(m); await db_session.commit()
    repo = EntregaRepository(db_session)
    assert await repo.reset_pendientes_interrumpidas() == 0
