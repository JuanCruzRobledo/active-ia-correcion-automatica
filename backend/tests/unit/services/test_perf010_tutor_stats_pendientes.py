"""PERF-010 — DashboardService.get_tutor_stats: pendientes por comisión.

Antes: la query agregada (details_query) daba total_alumnos por comisión, y LUEGO un
`SELECT COUNT(*) WHERE comision_id=X AND estado IN (SUBIDA, PENDIENTE)` por comisión en
loop. Ahora ese pendiente se agrega en la MISMA query con un COUNT condicional (case).

Regla de oro: los NÚMEROS del dashboard del tutor NO cambian —
- `pendientes` por comisión == COUNT de entregas SUBIDA/PENDIENTE de esa comisión,
- `alumnos` (total) por comisión sigue contando TODAS las entregas,
- los totales globales (pendientes/corregidas) intactos.

Real DB (SQLite) con las tablas necesarias. get_tutor_stats es un @staticmethod que
opera con `db` directo (sin repos), así que se ejercita contra una sesión real.
"""

import re

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.base import Base
from app.models.comision import Comision, ComisionTutor
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum, RolEnum
from app.models.materia import Materia
from app.models.usuario import Usuario
from app.services.dashboard_service import DashboardService

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL



@compiles(JSONB, "sqlite")
def _jsonb(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _reg(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "regexp_replace",
            3,
            lambda s, p, r: None if s is None else re.sub(p, r, s, count=1),
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def _entrega(db, comision_id, estado, i):
    db.add(
        Entrega(universidad_id=UNIV_ID, 
            comision_id=comision_id,
            rubrica_id=1,
            alumno_nombre=f"C{comision_id}-{estado.value}-{i}",
            archivo_nombre="tp.zip",
            archivo_tipo="zip",
            estado=estado,
        )
    )


@pytest_asyncio.fixture
async def tutor_con_comisiones(db_session):
    """Un tutor con 2 comisiones + una comisión de OTRO tutor (no debe aparecer).

    Comisión A: 2 SUBIDA, 1 PENDIENTE, 2 CORREGIDA, 1 ERROR → pendientes=3, alumnos=6
    Comisión B: 0 SUBIDA/PENDIENTE, 1 CORREGIDA          → pendientes=0, alumnos=1
    """
    materia = Materia(universidad_id=UNIV_ID, nombre="Programación 1", codigo="P1")
    db_session.add(materia)
    await db_session.flush()

    tutor = Usuario(username="tutor1", nombre="Tutor 1", password_hash="x", rol=RolEnum.TUTOR)
    otro = Usuario(username="tutor2", nombre="Tutor 2", password_hash="x", rol=RolEnum.TUTOR)
    db_session.add_all([tutor, otro])
    await db_session.flush()

    a = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    b = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-2", anio=2026, activa=True)
    ajena = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-9", anio=2026, activa=True)
    db_session.add_all([a, b, ajena])
    await db_session.flush()

    db_session.add_all(
        [
            ComisionTutor(comision_id=a.id, tutor_id=tutor.id),
            ComisionTutor(comision_id=b.id, tutor_id=tutor.id),
            ComisionTutor(comision_id=ajena.id, tutor_id=otro.id),
        ]
    )

    E = EstadoEntregaEnum
    for i in range(2):
        await _entrega(db_session, a.id, E.SUBIDA, i)
    await _entrega(db_session, a.id, E.PENDIENTE, 0)
    for i in range(2):
        await _entrega(db_session, a.id, E.CORREGIDA, i)
    await _entrega(db_session, a.id, E.ERROR, 0)
    await _entrega(db_session, b.id, E.CORREGIDA, 0)
    # comisión ajena con pendientes que NO deben sumar al tutor
    await _entrega(db_session, ajena.id, E.SUBIDA, 0)

    await db_session.commit()
    return {"tutor_id": tutor.id, "a": a.id, "b": b.id}


@pytest.mark.asyncio
async def test_pendientes_por_comision_en_query_agregada(db_session, tutor_con_comisiones):
    ids = tutor_con_comisiones
    stats = await DashboardService.get_tutor_stats(db_session, ids["tutor_id"])

    por_id = {d.id: d for d in stats.comisiones_details}
    assert stats.comisiones == 2

    # Comisión A: 6 entregas totales, 3 pendientes (2 SUBIDA + 1 PENDIENTE).
    assert por_id[ids["a"]].alumnos == 6
    assert por_id[ids["a"]].pendientes == 3

    # Comisión B: 1 entrega total, 0 pendientes.
    assert por_id[ids["b"]].alumnos == 1
    assert por_id[ids["b"]].pendientes == 0


@pytest.mark.asyncio
async def test_pendientes_por_comision_coinciden_con_count_por_comision(
    db_session, tutor_con_comisiones
):
    """Paridad con el loop viejo: el `pendientes` agregado == el COUNT filtrado por
    comisión que hacía el loop, comisión por comisión."""
    from sqlalchemy import func, select

    ids = tutor_con_comisiones
    stats = await DashboardService.get_tutor_stats(db_session, ids["tutor_id"])

    for d in stats.comisiones_details:
        esperado = await db_session.scalar(
            select(func.count(Entrega.id)).where(
                Entrega.comision_id == d.id,
                Entrega.estado.in_(
                    [EstadoEntregaEnum.SUBIDA, EstadoEntregaEnum.PENDIENTE]
                ),
            )
        )
        assert d.pendientes == esperado


@pytest.mark.asyncio
async def test_totales_globales_intactos(db_session, tutor_con_comisiones):
    ids = tutor_con_comisiones
    stats = await DashboardService.get_tutor_stats(db_session, ids["tutor_id"])

    # Global: pendientes = 3 (A) + 0 (B) = 3 ; corregidas = 2 (A) + 1 (B) = 3.
    assert stats.pendientes == 3
    assert stats.corregidas == 3


@pytest.mark.asyncio
async def test_tutor_sin_comisiones_devuelve_ceros(db_session):
    huerfano = Usuario(username="solo", nombre="Solo", password_hash="x", rol=RolEnum.TUTOR)
    db_session.add(huerfano)
    await db_session.commit()

    stats = await DashboardService.get_tutor_stats(db_session, huerfano.id)
    assert stats.comisiones == 0
    assert stats.pendientes == 0
    assert stats.corregidas == 0
    assert stats.comisiones_details == []
