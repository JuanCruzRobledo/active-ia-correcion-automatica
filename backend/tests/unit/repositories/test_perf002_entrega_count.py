"""PERF-002 (parte del count) — EntregaRepository.get_all.

El total del listado se calculaba con `select(func.count()).select_from(query.subquery())`,
arrastrando en el subquery las columnas pesadas (contenido_consolidado / pdf_contenido_b64)
y los selectinload. El fix lo cambia a `func.count(Entrega.id)` con los MISMOS filtros y
sin subquery de columnas.

Red de correctitud (regla de oro): el NÚMERO no cambia. Estos tests montan entregas en
distintos estados / archivadas / fechas y afirman que el `total` del count nuevo coincide
EXACTAMENTE con la cantidad real de filas que matchean cada filtro (equivalente a contar
el resultado del loop viejo).

SQLite en memoria con SOLO las tablas necesarias (patrón de test_orden_natural_comision.py).
"""

from datetime import date, datetime

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

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL



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


async def _seed(db) -> tuple[int, int]:
    """Dos comisiones con entregas variadas. Devuelve (comi_a_id, comi_b_id)."""
    materia = Materia(universidad_id=UNIV_ID, nombre="Programación 1", codigo="P1")
    db.add(materia)
    await db.flush()
    comi_a = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    comi_b = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1-2", anio=2026, activa=True)
    db.add_all([comi_a, comi_b])
    await db.flush()

    rid = 0

    def _mk(comi_id, estado, *, archivado=False, created=None):
        nonlocal rid
        rid += 1
        return Entrega(universidad_id=UNIV_ID, 
            comision_id=comi_id,
            rubrica_id=1,  # FK no forzada en SQLite; el count no la usa
            alumno_nombre=f"Alumno {rid}",
            archivo_nombre="tp.zip",
            archivo_tipo="zip",
            estado=estado,
            archivado=archivado,
            created_at=created or datetime(2026, 6, 10, 12, 0, 0),
        )

    entregas = [
        # Comisión A: 2 SUBIDA, 1 CORREGIDA, 1 ERROR, 1 archivada
        _mk(comi_a.id, EstadoEntregaEnum.SUBIDA),
        _mk(comi_a.id, EstadoEntregaEnum.SUBIDA),
        _mk(comi_a.id, EstadoEntregaEnum.CORREGIDA),
        _mk(comi_a.id, EstadoEntregaEnum.ERROR),
        _mk(comi_a.id, EstadoEntregaEnum.SUBIDA, archivado=True),
        # Comisión B: 1 SUBIDA (fecha vieja), 2 CORREGIDA
        _mk(comi_b.id, EstadoEntregaEnum.SUBIDA, created=datetime(2026, 1, 5, 9, 0, 0)),
        _mk(comi_b.id, EstadoEntregaEnum.CORREGIDA),
        _mk(comi_b.id, EstadoEntregaEnum.CORREGIDA),
    ]
    db.add_all(entregas)
    await db.commit()
    return comi_a.id, comi_b.id


@pytest.mark.asyncio
async def test_count_sin_filtros_excluye_archivadas(db_session):
    """Sin filtros: total == entregas NO archivadas (7 de 8)."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(per_page=100)
    assert total == 7
    assert len(entregas) == total  # el count coincide con las filas devueltas


@pytest.mark.asyncio
async def test_count_solo_archivadas(db_session):
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(solo_archivadas=True, per_page=100)
    assert total == 1
    assert len(entregas) == total


@pytest.mark.asyncio
async def test_count_incluyendo_archivadas(db_session):
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    _, total = await repo.get_all(include_archivadas=True, per_page=100)
    assert total == 8  # todas


@pytest.mark.asyncio
async def test_count_por_comision_y_por_estado(db_session):
    comi_a_id, comi_b_id = await _seed(db_session)
    repo = EntregaRepository(db_session)

    # Comisión A, no archivadas: 2 SUBIDA + 1 CORREGIDA + 1 ERROR = 4
    _, total_a = await repo.get_all(comision_id=comi_a_id, per_page=100)
    assert total_a == 4

    # Comisión B: 1 SUBIDA + 2 CORREGIDA = 3
    _, total_b = await repo.get_all(comision_id=comi_b_id, per_page=100)
    assert total_b == 3

    # Filtro por estado CORREGIDA (todas las comisiones): 1 (A) + 2 (B) = 3
    _, total_corr = await repo.get_all(estado=EstadoEntregaEnum.CORREGIDA, per_page=100)
    assert total_corr == 3


@pytest.mark.asyncio
async def test_count_respeta_rango_de_fechas(db_session):
    await _seed(db_session)
    repo = EntregaRepository(db_session)

    # Sólo la entrega de enero (comisión B) queda fuera del rango junio.
    _, total_junio = await repo.get_all(
        fecha_desde=date(2026, 6, 1), fecha_hasta=date(2026, 6, 30), per_page=100
    )
    # 7 no archivadas totales - 1 de enero = 6
    assert total_junio == 6


@pytest.mark.asyncio
async def test_count_con_paginacion_no_depende_de_per_page(db_session):
    """El total refleja TODAS las filas que matchean, no sólo la página devuelta."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)
    entregas, total = await repo.get_all(page=1, per_page=2)
    assert total == 7  # total real
    assert len(entregas) == 2  # sólo la página
