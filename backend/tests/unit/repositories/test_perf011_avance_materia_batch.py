"""PERF-011 — batching de las lecturas del Dashboard de Gestores.

Cubre los métodos de repo NUEVOS que reemplazan los loops con query adentro:

- AvanceRepository.get_ultimos_snapshots(materia_ids): el snapshot MÁS RECIENTE de
  cada materia en UNA query (window row_number), reemplazando get_ultimo_snapshot por
  materia. Debe devolver, para cada materia, el MISMO snapshot que get_ultimo_snapshot.
- MateriaRepository.get_by_cuatrimestres(cuatri_ids): materias activas de varios
  cuatrimestres en UNA query, reemplazando get_by_cuatrimestre por cuatrimestre.

Nota (deliverable): se eligió una ventana `row_number()` en vez del `DISTINCT ON`
Postgres-only justamente para poder ejercitar el repo REAL contra el harness SQLite
in-memory (SQLite soporta window functions desde 3.25). Así el test valida la
selección latest-por-materia de verdad, no sólo la lógica del service con mocks.
"""

import re
from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.models.avance import AvanceSnapshot
from app.models.base import Base
from app.models.cohorte import Cohorte, Cuatrimestre
from app.models.materia import Materia
from app.repositories.avance_repository import AvanceRepository
from app.repositories.materia_repository import MateriaRepository

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


async def _snap(db, materia_id, generado_en, total=0) -> AvanceSnapshot:
    s = AvanceSnapshot(universidad_id=UNIV_ID, 
        materia_id=materia_id, generado_en=generado_en, total_alumnos=total
    )
    db.add(s)
    await db.flush()
    return s


# ---------------------------------------------------------------------------
# AvanceRepository.get_ultimos_snapshots
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_ultimos_snapshots_uno_por_materia_el_mas_reciente(db_session):
    m1 = Materia(universidad_id=UNIV_ID, nombre="Prog 1", codigo="P1")
    m2 = Materia(universidad_id=UNIV_ID, nombre="Prog 2", codigo="P2")
    m3_sin = Materia(universidad_id=UNIV_ID, nombre="Redes", codigo="RED")  # sin snapshots
    db_session.add_all([m1, m2, m3_sin])
    await db_session.flush()

    # m1: 3 snapshots; el de junio 5 es el más reciente.
    await _snap(db_session, m1.id, datetime(2026, 6, 1), total=10)
    s_m1_ultimo = await _snap(db_session, m1.id, datetime(2026, 6, 5), total=12)
    await _snap(db_session, m1.id, datetime(2026, 6, 3), total=11)
    # m2: 1 snapshot.
    s_m2 = await _snap(db_session, m2.id, datetime(2026, 5, 20), total=7)
    await db_session.commit()

    repo = AvanceRepository(db_session)
    result = await repo.get_ultimos_snapshots([m1.id, m2.id, m3_sin.id])

    por_materia = {s.materia_id: s for s in result}
    # Una fila por materia CON snapshot; la materia sin snapshot no aparece.
    assert set(por_materia.keys()) == {m1.id, m2.id}
    assert por_materia[m1.id].id == s_m1_ultimo.id
    assert por_materia[m1.id].total_alumnos == 12
    assert por_materia[m2.id].id == s_m2.id


@pytest.mark.asyncio
async def test_get_ultimos_snapshots_coincide_con_get_ultimo_snapshot(db_session):
    """Paridad: para cada materia, get_ultimos_snapshots devuelve el MISMO snapshot
    que el get_ultimo_snapshot del loop viejo."""
    m1 = Materia(universidad_id=UNIV_ID, nombre="Prog 1", codigo="P1")
    m2 = Materia(universidad_id=UNIV_ID, nombre="Prog 2", codigo="P2")
    db_session.add_all([m1, m2])
    await db_session.flush()
    await _snap(db_session, m1.id, datetime(2026, 6, 1))
    await _snap(db_session, m1.id, datetime(2026, 6, 9))
    await _snap(db_session, m2.id, datetime(2026, 4, 1))
    await db_session.commit()

    repo = AvanceRepository(db_session)
    batch = {s.materia_id: s.id for s in await repo.get_ultimos_snapshots([m1.id, m2.id])}
    for mid in (m1.id, m2.id):
        viejo = await repo.get_ultimo_snapshot(mid)
        assert batch[mid] == viejo.id


@pytest.mark.asyncio
async def test_get_ultimos_snapshots_lista_vacia(db_session):
    repo = AvanceRepository(db_session)
    assert await repo.get_ultimos_snapshots([]) == []


# ---------------------------------------------------------------------------
# MateriaRepository.get_by_cuatrimestres
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_get_by_cuatrimestres_agrupa_y_coincide_con_por_cuatrimestre(db_session):
    cohorte = Cohorte(codigo="M26", nombre="M26")
    db_session.add(cohorte)
    await db_session.flush()
    q1 = Cuatrimestre(nombre="1C", cohorte_id=cohorte.id, numero=1)
    q2 = Cuatrimestre(nombre="2C", cohorte_id=cohorte.id, numero=2)
    db_session.add_all([q1, q2])
    await db_session.flush()

    # q1: 2 materias activas + 1 inactiva (no debe aparecer). q2: 1 materia.
    db_session.add_all(
        [
            Materia(universidad_id=UNIV_ID, nombre="Beta", codigo="B", cuatrimestre_id=q1.id, activa=True),
            Materia(universidad_id=UNIV_ID, nombre="Alfa", codigo="A", cuatrimestre_id=q1.id, activa=True),
            Materia(universidad_id=UNIV_ID, nombre="Zeta", codigo="Z", cuatrimestre_id=q1.id, activa=False),
            Materia(universidad_id=UNIV_ID, nombre="Gamma", codigo="G", cuatrimestre_id=q2.id, activa=True),
        ]
    )
    await db_session.commit()

    repo = MateriaRepository(db_session)
    todas = await repo.get_by_cuatrimestres([q1.id, q2.id])

    por_cuatri: dict[int, list[str]] = {}
    for m in todas:
        por_cuatri.setdefault(m.cuatrimestre_id, []).append(m.nombre)

    # Sólo activas; q1 ordenada por nombre asc (Alfa, Beta).
    assert por_cuatri[q1.id] == ["Alfa", "Beta"]
    assert por_cuatri[q2.id] == ["Gamma"]

    # Paridad con el método por cuatrimestre (mismo conjunto y orden).
    for qid in (q1.id, q2.id):
        viejo = [m.nombre for m in await repo.get_by_cuatrimestre(qid)]
        assert por_cuatri[qid] == viejo


@pytest.mark.asyncio
async def test_get_by_cuatrimestres_lista_vacia(db_session):
    repo = MateriaRepository(db_session)
    assert await repo.get_by_cuatrimestres([]) == []
