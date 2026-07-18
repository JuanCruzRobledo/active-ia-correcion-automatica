"""PERF-002 (parte defer) + PERF-006 — columnas GIGANTES marcadas `deferred=True`.

Se defirieron tres columnas que se arrastraban en cada `select()` sin necesidad:
  - Entrega.contenido_consolidado (código completo, Text)
  - Entrega.pdf_contenido_b64      (PDF en Base64, Text ~MB)
  - Correccion.raw_response        (respuesta cruda de Gemini, JSONB)

TEST A (defer efectivo): un listado / lectura por defecto NO trae esas columnas
(quedan en `inspect(obj).unloaded`), mientras que las columnas que SÍ se muestran
siempre (contenido_preview, nota, criterios_json) siguen cargadas.

TEST B (no-regresión, regla de oro): los flujos que SÍ necesitan el contenido lo
siguen leyendo idéntico:
  - EntregaService.obtener_contenido → devuelve el código / el PDF correcto (undefer
    vía get_by_id(load_contenido=True)).
  - EntregaRepository.get_by_id_with_relations(load_contenido=True) → la corrección
    puede leer contenido_consolidado / pdf_contenido_b64 sin MissingGreenlet.
  - undefer(Correccion.raw_response) recupera el JSONB tal cual (dato no perdido).

SQLite en memoria con sólo las tablas necesarias (patrón de test_perf002_entrega_count.py).
"""

import base64
import json
import sqlite3

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY, inspect, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker, undefer

# sqlite3 no sabe bindear dict/list (JSONB/ARRAY) directamente; con estos adapters el
# driver los serializa a JSON en el INSERT y el result_processor de JSONB los devuelve
# como dict/list al leer — así el round-trip de criterios_json / raw_response es real.
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)

from app.models.base import Base
from app.models.comision import Comision, ComisionTutor
from app.models.correccion import Correccion
from app.models.entrega import Entrega, EntregaHistorial
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.models.usuario import Usuario
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.services.entrega_service import EntregaService


# SQLite no soporta ARRAY/JSONB nativos; se compilan a JSON sólo en el dialecto de tests.
@compiles(JSONB, "sqlite")
def _jsonb_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


CODIGO_CONSOLIDADO = "# archivo main.py\nprint('hola mundo')\n" * 50
PDF_B64 = base64.b64encode(b"%PDF-1.4 fake pdf bytes " * 100).decode("utf-8")
RAW_GEMINI = {"model": "gemini-2.0-flash", "candidates": [{"text": "..."}], "n": 7}


@pytest_asyncio.fixture
async def db_session():
    # Se importan todos los modelos y se crean TODAS las tablas: get_by_id_with_relations
    # dispara selectinload en cascada (comisión→materia y sus relaciones eager), así que
    # filtrar tablas sería un juego de "falta esta tabla". Crear el esquema completo es
    # más simple y no cambia lo que se está probando.
    import app.models  # noqa: F401 — puebla el registry de mappers/tablas

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def _seed(db) -> dict:
    """Una entrega de código, una entrega PDF y una corrección con raw_response."""
    materia = Materia(nombre="Programación 1", codigo="P1")
    db.add(materia)
    await db.flush()
    comi = Comision(materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    db.add(comi)
    await db.flush()
    rubrica = Rubrica(
        materia_id=materia.id,
        titulo="TP1",
        descripcion="Rúbrica de prueba",
        numero=1,
        anio=2026,
        tipo="TP",
        puntaje_maximo=100,
        criterios_json=[],
    )
    db.add(rubrica)
    await db.flush()

    entrega_codigo = Entrega(
        comision_id=comi.id,
        rubrica_id=rubrica.id,
        alumno_nombre="Ada Lovelace",
        archivo_nombre="tp.zip",
        archivo_ruta="/tmp/tp.zip",
        archivo_tipo="zip",
        contenido_preview="print('hola'...",
        contenido_consolidado=CODIGO_CONSOLIDADO,
        archivos_incluidos=None,
        estado=EstadoEntregaEnum.SUBIDA,
    )
    entrega_pdf = Entrega(
        comision_id=comi.id,
        rubrica_id=rubrica.id,
        alumno_nombre="Alan Turing",
        archivo_nombre="parcial.pdf",
        archivo_ruta="/tmp/parcial.pdf",
        archivo_tipo="pdf",
        contenido_preview="[Entrega en formato PDF]",
        pdf_contenido_b64=PDF_B64,
        archivos_incluidos=None,
        estado=EstadoEntregaEnum.SUBIDA,
    )
    db.add_all([entrega_codigo, entrega_pdf])
    await db.flush()

    correccion = Correccion(
        entrega_id=entrega_codigo.id,
        nota=85,
        criterios_json={"criterios": [{"id": "c1", "puntaje_obtenido": 85}]},
        raw_response=RAW_GEMINI,
    )
    db.add(correccion)
    await db.commit()

    ids = {
        "codigo": entrega_codigo.id,
        "pdf": entrega_pdf.id,
        "correccion": correccion.id,
    }
    # Vaciar el identity map: sin esto, las queries devuelven los MISMOS objetos ya
    # poblados en memoria (expire_on_commit=False) y el defer no se observaría.
    db.expunge_all()
    return ids


# ---------------------------------------------------------------------------
# TEST A — el defer es efectivo: las columnas gigantes NO se cargan por defecto
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_listado_no_carga_columnas_gigantes_de_entrega(db_session):
    """get_all (listado) deja contenido_consolidado y pdf_contenido_b64 deferidos."""
    await _seed(db_session)
    repo = EntregaRepository(db_session)

    entregas, _ = await repo.get_all(per_page=100)
    assert len(entregas) == 2

    for entrega in entregas:
        unloaded = inspect(entrega).unloaded
        # Las gigantes NO vienen en el listado.
        assert "contenido_consolidado" in unloaded
        assert "pdf_contenido_b64" in unloaded
        # Control: la columna corta que SÍ se muestra en la tabla sigue cargada.
        assert "contenido_preview" not in unloaded
        assert "estado" not in unloaded


@pytest.mark.asyncio
async def test_get_by_id_sin_flag_deja_gigantes_deferidas(db_session):
    """get_by_id por defecto (load_contenido=False) tampoco las trae."""
    ids = await _seed(db_session)
    repo = EntregaRepository(db_session)

    entrega = await repo.get_by_id(ids["codigo"])
    unloaded = inspect(entrega).unloaded
    assert "contenido_consolidado" in unloaded
    assert "pdf_contenido_b64" in unloaded


@pytest.mark.asyncio
async def test_correccion_no_carga_raw_response_por_defecto(db_session):
    """Leer una corrección no arrastra raw_response, pero sí la nota y los criterios."""
    ids = await _seed(db_session)
    repo = CorreccionRepository(db_session)

    correccion = await repo.get_by_id(ids["correccion"])
    unloaded = inspect(correccion).unloaded
    assert "raw_response" in unloaded
    # Control: la NOTA desglosada se lee SIEMPRE que se muestra la corrección → NO deferida.
    assert "criterios_json" not in unloaded
    assert "nota" not in unloaded


# ---------------------------------------------------------------------------
# TEST B — no-regresión: los flujos que necesitan el contenido lo leen igual
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_obtener_contenido_codigo_devuelve_consolidado(db_session):
    """EntregaService.obtener_contenido sirve el código consolidado (undefer)."""
    ids = await _seed(db_session)
    service = EntregaService(db_session)

    contenido = await service.obtener_contenido(ids["codigo"])

    assert contenido.es_pdf is False
    assert contenido.contenido_consolidado == CODIGO_CONSOLIDADO
    assert contenido.pdf_contenido_b64 is None
    assert contenido.total_caracteres == len(CODIGO_CONSOLIDADO)


@pytest.mark.asyncio
async def test_obtener_contenido_pdf_devuelve_base64(db_session):
    """EntregaService.obtener_contenido sirve el PDF en Base64 (undefer)."""
    ids = await _seed(db_session)
    service = EntregaService(db_session)

    contenido = await service.obtener_contenido(ids["pdf"])

    assert contenido.es_pdf is True
    assert contenido.pdf_contenido_b64 == PDF_B64
    assert contenido.contenido_consolidado is None


@pytest.mark.asyncio
async def test_get_by_id_with_relations_undefer_permite_leer_contenido(db_session):
    """La corrección arma su payload leyendo contenido/pdf sin MissingGreenlet."""
    ids = await _seed(db_session)
    repo = EntregaRepository(db_session)

    entrega_codigo = await repo.get_by_id_with_relations(
        ids["codigo"], load_contenido=True
    )
    # Ya cargada (no en unloaded) y con el valor correcto — este es el acceso exacto
    # que hace _build_correction_payload.
    assert "contenido_consolidado" not in inspect(entrega_codigo).unloaded
    assert entrega_codigo.contenido_consolidado == CODIGO_CONSOLIDADO

    entrega_pdf = await repo.get_by_id_with_relations(ids["pdf"], load_contenido=True)
    assert "pdf_contenido_b64" not in inspect(entrega_pdf).unloaded
    assert entrega_pdf.pdf_contenido_b64 == PDF_B64


@pytest.mark.asyncio
async def test_raw_response_recuperable_con_undefer(db_session):
    """El dato de raw_response no se pierde: undefer lo trae idéntico."""
    ids = await _seed(db_session)

    result = await db_session.execute(
        select(Correccion)
        .options(undefer(Correccion.raw_response))
        .where(Correccion.id == ids["correccion"])
    )
    correccion = result.scalar_one()
    assert "raw_response" not in inspect(correccion).unloaded
    assert correccion.raw_response == RAW_GEMINI
