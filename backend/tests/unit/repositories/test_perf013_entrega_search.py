"""PERF-013 (búsqueda de entregas en el backend) — EntregaRepository.get_all.

El frontend manda `search` a GET /entregas, pero el backend NO lo declaraba, así que
FastAPI lo descartaba: la búsqueda no filtraba nada y todas las páginas cacheaban igual.

El fix declara `search` en el endpoint, lo baja al repo y ahí filtra por
`Entrega.alumno_nombre.ilike("%search%")`. El filtro se suma a la MISMA lista
`conditions` que comparten la query de datos y la de count (PERF-002), así el `total`
refleja el filtro igual que las filas devueltas.

Red de correctitud:
- (a) con search filtra por nombre PARCIAL y case-insensitive,
- (b) el `total` (count) refleja el filtro,
- (c) sin search trae TODO (paridad con el comportamiento actual).

SQLite en memoria con SOLO las tablas necesarias (mismo patrón que test_perf002_entrega_count.py).
"""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.comision import Comision, ComisionTutor
from app.models.correccion import Correccion
from app.models.entrega import Entrega, EntregaHistorial
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.usuario import Usuario
from app.repositories.entrega_repository import EntregaRepository


# SQLite no soporta ARRAY/JSONB nativos; se compilan a JSON sólo en el dialecto de tests.
@compiles(JSONB, "sqlite")
def _jsonb_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    tablas = [
        Usuario.__table__,
        Materia.__table__,
        Comision.__table__,
        ComisionTutor.__table__,
        Rubrica.__table__,
        Entrega.__table__,
        EntregaHistorial.__table__,
        Correccion.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tablas)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def _seed(db) -> int:
    """Una comisión con 4 alumnos de nombres variados. Devuelve comision_id."""
    materia = Materia(nombre="Programación 1", codigo="P1")
    db.add(materia)
    await db.flush()
    comi = Comision(materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    db.add(comi)
    await db.flush()

    rid = 0

    def _mk(nombre):
        nonlocal rid
        rid += 1
        return Entrega(
            comision_id=comi.id,
            rubrica_id=1,  # FK no forzada en SQLite
            alumno_nombre=nombre,
            archivo_nombre="tp.zip",
            archivo_tipo="zip",
            estado=EstadoEntregaEnum.SUBIDA,
            archivado=False,
            created_at=datetime(2026, 6, 10, 12, 0, 0),
        )

    db.add_all([
        _mk("Juan Pérez"),
        _mk("María García"),
        _mk("Juana Gómez"),
        _mk("Carlos López"),
    ])
    await db.commit()
    return comi.id


@pytest.mark.asyncio
async def test_search_filtra_por_nombre_parcial_case_insensitive(db_session):
    """(a) 'jua' matchea 'Juan Pérez' y 'Juana Gómez', ignorando mayúsculas."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(search="jua", per_page=100)
    nombres = sorted(e.alumno_nombre for e in entregas)
    assert nombres == ["Juan Pérez", "Juana Gómez"]
    # (b) el count refleja el filtro, no el total real de la tabla
    assert total == 2


@pytest.mark.asyncio
async def test_search_count_coincide_con_filas(db_session):
    """(b) el total del count coincide EXACTAMENTE con las filas filtradas."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(search="garcía", per_page=100)
    assert total == 1
    assert len(entregas) == total
    assert entregas[0].alumno_nombre == "María García"


@pytest.mark.asyncio
async def test_search_sin_resultados(db_session):
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(search="zzz-no-existe", per_page=100)
    assert total == 0
    assert entregas == []


@pytest.mark.asyncio
async def test_sin_search_trae_todo_paridad(db_session):
    """(c) sin search (None) el comportamiento es idéntico al actual: todas las filas."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    _, total_none = await repo.get_all(per_page=100)
    assert total_none == 4


@pytest.mark.asyncio
async def test_search_vacio_o_espacios_no_filtra(db_session):
    """search='' o '   ' se trata como 'sin búsqueda' → no filtra (paridad)."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    _, total_vacio = await repo.get_all(search="", per_page=100)
    _, total_espacios = await repo.get_all(search="   ", per_page=100)
    assert total_vacio == 4
    assert total_espacios == 4


@pytest.mark.asyncio
async def test_search_se_combina_con_otros_filtros(db_session):
    """El search se suma a los filtros existentes sin romperlos (AND con estado)."""
    comi_id = await _seed(db_session)
    repo = EntregaRepository(db_session)
    # 'gó/go' matchea "Juana Gómez"; combinado con comisión y estado SUBIDA sigue dando 1.
    entregas, total = await repo.get_all(
        comision_id=comi_id,
        estado=EstadoEntregaEnum.SUBIDA,
        search="gómez",
        per_page=100,
    )
    assert total == 1
    assert entregas[0].alumno_nombre == "Juana Gómez"
