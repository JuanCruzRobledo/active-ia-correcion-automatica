"""PERF-003 — el ZIP de devoluciones no re-consulta por id (N+1) y renderiza en un thread.

Antes, ``generar_zip_pdfs`` traía las correcciones con ``get_all`` y DENTRO del loop volvía
a consultar cada una por id (``generar_pdf_devolucion`` → ``get_by_id_with_relations``):
un N+1 clásico. Además el render reportlab de cada PDF corría inline, bloqueando el event
loop con 100+ PDFs.

El fix: materializar cada corrección YA cargada a un snapshot plano (sin ORM/lazy) y
renderizar el ZIP entero en una función pura-CPU envuelta en ``asyncio.to_thread``.

- N+1: monkeypatcheamos ``get_by_id_with_relations`` y ``get_by_id`` del repo para que
  EXPLOTEN si se las llama. El ZIP debe generarse igual → prueba que ya no se re-consulta
  por id.
- Render en thread sin MissingGreenlet: al sembrar SQLite async y renderizar dentro de
  ``asyncio.to_thread``, cualquier acceso lazy al ORM dentro del thread reventaría con
  MissingGreenlet. Que el ZIP salga con PDFs válidos prueba que la materialización previa
  es completa.
"""

import io
import json
import sqlite3
import zipfile
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# sqlite3 no bindea dict/list (JSONB/ARRAY) directo; estos adapters los serializan a JSON.
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)

from app.models.base import Base
from app.models.comision import Comision
from app.models.correccion import Correccion
from app.models.entrega import Entrega
from app.models.enums import EstadoEntregaEnum
from app.models.materia import Materia
from app.models.rubrica import Rubrica
from app.services.pdf_service import PDFService


@compiles(JSONB, "sqlite")
def _jsonb_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json_en_sqlite(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    import app.models  # noqa: F401 — puebla el registry de mappers/tablas

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


async def _seed(db, *, n: int) -> dict:
    """Materia + comisión + rúbrica + ``n`` entregas CORREGIDA con su Correccion."""
    materia = Materia(nombre="Programación 1", codigo="P1")
    db.add(materia)
    await db.flush()
    comi = Comision(materia_id=materia.id, nombre="C1-1", anio=2026, activa=True)
    db.add(comi)
    await db.flush()
    rubrica = Rubrica(
        materia_id=materia.id,
        titulo="Trabajo Práctico 1",
        descripcion="Rúbrica de prueba",
        numero=1,
        anio=2026,
        tipo="TP",
        puntaje_maximo=100,
        criterios_json=[],
    )
    db.add(rubrica)
    await db.flush()

    entregas = [
        Entrega(
            comision_id=comi.id,
            rubrica_id=rubrica.id,
            alumno_nombre=f"Alumno {i:03d}",
            archivo_nombre=f"tp{i}.zip",
            archivo_ruta=f"/tmp/tp{i}.zip",
            archivo_tipo="zip",
            contenido_preview="print('hola')",
            estado=EstadoEntregaEnum.CORREGIDA,
        )
        for i in range(n)
    ]
    db.add_all(entregas)
    await db.flush()

    entrega_ids = [e.id for e in entregas]
    for e in entregas:
        db.add(
            Correccion(
                entrega_id=e.id,
                nota=Decimal("88"),
                criterios_json={
                    "criterios": [
                        {
                            "nombre": "Funcionalidad",
                            "puntaje_obtenido": 35,
                            "puntaje_maximo": 40,
                            "estado": "WARNING",
                            "feedback": "Casi",
                        }
                    ]
                },
                fortalezas=["Código claro"],
                recomendaciones=["Agregar tests"],
                comentario_general="Buen trabajo",
                editado_manualmente=False,
            )
        )
    await db.commit()
    return {
        "comision_id": comi.id,
        "rubrica_id": rubrica.id,
        "entrega_ids": entrega_ids,
    }


def _armar_bomba(service: PDFService) -> dict:
    """Reemplaza las consultas por-id del repo por versiones que EXPLOTAN.

    Si el ZIP se genera igual, es porque no se re-consulta cada corrección por id.
    """
    estado = {"por_id_llamado": False}

    async def boom_por_id(*_args, **_kwargs):
        estado["por_id_llamado"] = True
        raise AssertionError(
            "regresión PERF-003 (N+1): el ZIP re-consultó una corrección por id"
        )

    service.correccion_repo.get_by_id_with_relations = boom_por_id
    service.correccion_repo.get_by_id = boom_por_id
    return estado


@pytest.mark.asyncio
async def test_generar_zip_pdfs_no_reconsulta_por_id(db_session):
    """El ZIP de una comisión/rúbrica NO llama get_by_id_* por corrección (sin N+1)."""
    ids = await _seed(db_session, n=4)
    service = PDFService(db_session)
    espia = _armar_bomba(service)

    zip_bytes, filename = await service.generar_zip_pdfs(
        comision_id=ids["comision_id"], rubrica_id=ids["rubrica_id"]
    )

    assert espia["por_id_llamado"] is False
    assert filename.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        nombres = zf.namelist()
        assert len(nombres) == 4
        # PDFs válidos → la materialización previa al thread fue completa (sin MissingGreenlet).
        for nombre in nombres:
            assert zf.read(nombre).startswith(b"%PDF")


@pytest.mark.asyncio
async def test_generar_zip_pdfs_seleccionados_no_reconsulta_por_id(db_session):
    """El ZIP de entregas seleccionadas tampoco re-consulta por id."""
    ids = await _seed(db_session, n=3)
    service = PDFService(db_session)
    espia = _armar_bomba(service)

    zip_bytes, filename = await service.generar_zip_pdfs_seleccionados(
        entrega_ids=ids["entrega_ids"]
    )

    assert espia["por_id_llamado"] is False
    assert "Seleccionados" in filename
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        assert len(zf.namelist()) == 3
        for nombre in zf.namelist():
            assert zf.read(nombre).startswith(b"%PDF")


@pytest.mark.asyncio
async def test_zip_pdf_contiene_nombre_alumno_saneado(db_session):
    """Cada PDF del ZIP se nombra AlumnoNombre-Devolucion-TP-1.pdf (datos del snapshot)."""
    ids = await _seed(db_session, n=2)
    service = PDFService(db_session)

    zip_bytes, _filename = await service.generar_zip_pdfs(
        comision_id=ids["comision_id"], rubrica_id=ids["rubrica_id"]
    )

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        nombres = zf.namelist()
    # "Alumno 000" → "Alumno-000"; rúbrica TP número 1 → "TP-1".
    assert any(n == "Alumno-000-Devolucion-TP-1.pdf" for n in nombres)
    assert any(n == "Alumno-001-Devolucion-TP-1.pdf" for n in nombres)
