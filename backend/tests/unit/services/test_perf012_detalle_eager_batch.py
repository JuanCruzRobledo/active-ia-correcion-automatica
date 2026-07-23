"""PERF-012 — Eliminar el get_by_id-por-elemento en loops.

Dos superficies:

1. ComisionService.obtener_comision: antes hacía `usuario_repo.get_by_id(ct.tutor_id)`
   por cada tutor de la comisión; ahora el usuario viene eager-loaded (ct.tutor) en
   `get_by_id_with_relations`. El detalle de tutores (id/username/nombre/asignado_en)
   NO cambia.

2. MateriaService.listar_materias: antes contaba coordinadores con
   `get_coordinadores_for_materia(id)` por materia; ahora UNA query agregada. El
   num_coordinadores por materia NO cambia.

Real DB (SQLite) con metadata completa (shims JSONB/ARRAY) para cubrir cascadas ORM.
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
from app.models.enums import RolEnum
from app.models.materia import CoordinadorMateria, Materia
from app.models.usuario import Usuario
from app.services.comision_service import ComisionService
from app.services.materia_service import MateriaService

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


async def _usuario(db, username, rol) -> Usuario:
    # `rol` ya no se persiste en `Usuario` (Fase 6 multi-tenant): se conserva
    # el parámetro por compatibilidad de firma con los callers, pero ningún
    # test de este archivo lee `.rol` (verificado) — no hace falta membresía.
    u = Usuario(username=username, nombre=f"N {username}", password_hash="x")
    db.add(u)
    await db.flush()
    return u


# ---------------------------------------------------------------------------
# Superficie 1: obtener_comision con tutores eager-loaded
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_obtener_comision_tutores_eager_sin_get_by_id_en_loop(db_session, monkeypatch):
    materia = Materia(universidad_id=UNIV_ID, nombre="Programación 1", codigo="P1")
    db_session.add(materia)
    await db_session.flush()
    t1 = await _usuario(db_session, "tutor1", RolEnum.TUTOR)
    t2 = await _usuario(db_session, "tutor2", RolEnum.TUTOR)
    comi = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    db_session.add(comi)
    await db_session.flush()
    db_session.add_all(
        [
            ComisionTutor(comision_id=comi.id, tutor_id=t1.id),
            ComisionTutor(comision_id=comi.id, tutor_id=t2.id),
        ]
    )
    await db_session.commit()

    service = ComisionService(db_session)

    # Regla de oro sobre la implementación: NO se debe llamar get_by_id por tutor.
    async def _boom(*a, **k):
        raise AssertionError("obtener_comision no debe usar usuario_repo.get_by_id (N+1)")

    monkeypatch.setattr(service.usuario_repo, "get_by_id", _boom)

    detail = await service.obtener_comision(comi.id)

    ids = {t.id for t in detail.tutores}
    nombres = {t.username for t in detail.tutores}
    assert ids == {t1.id, t2.id}
    assert nombres == {"tutor1", "tutor2"}
    assert len(detail.tutores) == 2
    # asignado_en (de ComisionTutor) presente en cada tutor.
    assert all(t.asignado_en is not None for t in detail.tutores)


@pytest.mark.asyncio
async def test_obtener_comision_sin_tutores(db_session):
    materia = Materia(universidad_id=UNIV_ID, nombre="Álgebra", codigo="ALG")
    db_session.add(materia)
    await db_session.flush()
    comi = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    db_session.add(comi)
    await db_session.commit()

    detail = await ComisionService(db_session).obtener_comision(comi.id)
    assert detail.tutores == []


# ---------------------------------------------------------------------------
# Superficie 2: listar_materias con conteo de coordinadores batcheado
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_listar_materias_num_coordinadores_identico_al_loop(db_session):
    c1 = await _usuario(db_session, "coord1", RolEnum.COORDINADOR)
    c2 = await _usuario(db_session, "coord2", RolEnum.COORDINADOR)

    m_dos = Materia(universidad_id=UNIV_ID, nombre="Programación 1", codigo="P1")
    m_uno = Materia(universidad_id=UNIV_ID, nombre="Programación 2", codigo="P2")
    m_cero = Materia(universidad_id=UNIV_ID, nombre="Redes", codigo="RED")
    db_session.add_all([m_dos, m_uno, m_cero])
    await db_session.flush()

    db_session.add_all(
        [
            CoordinadorMateria(coordinador_id=c1.id, materia_id=m_dos.id),
            CoordinadorMateria(coordinador_id=c2.id, materia_id=m_dos.id),
            CoordinadorMateria(coordinador_id=c1.id, materia_id=m_uno.id),
        ]
    )
    await db_session.commit()

    service = MateriaService(db_session)
    result = await service.listar_materias(per_page=50)
    por_id = {item.id: item for item in result.items}

    assert por_id[m_dos.id].num_coordinadores == 2
    assert por_id[m_uno.id].num_coordinadores == 1
    assert por_id[m_cero.id].num_coordinadores == 0

    # Paridad explícita con el método del loop viejo.
    for item in result.items:
        viejo = await service.coord_materia_repo.get_coordinadores_for_materia(item.id)
        assert item.num_coordinadores == len(viejo)
