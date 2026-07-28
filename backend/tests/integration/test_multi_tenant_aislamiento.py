"""
GATE de aislamiento multi-tenant (Fase 4, multi-tenant-scoping-queries, tasks §11).

Crea DOS universidades (UniA=1, UniB=2) con un árbol de datos completo cada una
(materia → comisión → entrega → corrección, + unidad, rúbrica, examen, cierre de
cursada, snapshot de avance) contra la DB real de la suite (SQLite in-memory,
`db_session`), y verifica el invariante central de esta fase:

  - Un usuario de UniA NO ve NADA de UniB: los listados de las 9 entidades
    scopeadas devuelven vacío para UniB, y el acceso por id a un recurso de
    UniB responde 404 (no 403 — indistinguible de "no existe").
  - Un superadmin SIN universidad activa (`universidad_id is None`) ve AMBAS
    universidades en los listados.
  - Un superadmin CON universidad elegida queda scopeado a esa universidad,
    igual que cualquier miembro (D5/OQ2).

No pasa por la capa HTTP (no arma el stack de auth/ASGI completo): ejercita
directamente repositories + services, que es donde vive el filtro real
(ARCH-001: el WHERE está en el repository). Los routers son wiring fino
(pasan `ctx.universidad_id`) ya cubierto por los tests unitarios de cada router.
"""

from datetime import datetime, date
from decimal import Decimal
import json
import re
import sqlite3

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import ARRAY, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

# sqlite3 no sabe bindear dict/list (JSONB/ARRAY de Postgres) directamente; con estos
# adapters el driver los serializa a JSON en el INSERT — mismo patrón que
# test_perf006_defer_columnas_gigantes.py.
sqlite3.register_adapter(dict, json.dumps)
sqlite3.register_adapter(list, json.dumps)

from app.core.permissions import verificar_pertenencia_universidad
from app.models.avance import AvanceAlumno, AvanceSnapshot
from app.models.base import Base
from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.comision import Comision, ComisionTutor
from app.models.correccion import Correccion
from app.models.entrega import Entrega, EntregaHistorial
from app.models.enums import (
    EstadoEntregaEnum,
    FuenteRubricaEnum,
    ModoAprobacionEnum,
    RolEnum,
    TipoActividadMoodleEnum,
    TipoExamenEnum,
    TipoRubricaEnum,
)
from app.models.componente_unidad import ComponenteUnidad
from app.models.examen_materia import ExamenMateria
from app.models.materia import CoordinadorMateria, Materia
from app.models.rubrica import Rubrica
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.repositories.avance_repository import AvanceRepository
from app.repositories.cierre_cursada_repository import CierreCursadaRepository
from app.repositories.comision_repository import ComisionRepository
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.examen_repository import ExamenRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.unidad_repository import UnidadRepository
from app.services.comision_service import ComisionService
from app.services.correccion_service import CorreccionService
from app.services.entrega_service import EntregaService
from app.services.examen_service import ExamenService
from app.services.materia_service import MateriaService
from app.services.rubrica_service import RubricaService
from app.services.unidad_service import UnidadService

UNI_A = 1
UNI_B = 2


# SQLite no tiene JSONB/ARRAY nativos; se compilan como JSON (mismo comportamiento
# observable). Patrón calcado de tests/unit/repositories/test_crud001_soft_delete.py
# — necesario acá porque este archivo puede correr aislado (sin que otro módulo ya
# haya registrado el shim globalmente).
@compiles(JSONB, "sqlite")
def _jsonb_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


def _regexp_replace_sqlite(source, pattern: str, replacement: str):
    """UDF que replica `regexp_replace` de Postgres (usado por `orden_natural_sql`
    en comision_repository.get_all). Shim calcado de test_orden_natural_comision.py
    — solo afecta esta conexión SQLite de test, no producción."""
    if source is None:
        return None
    return re.sub(pattern, replacement, source, count=1)


@pytest_asyncio.fixture
async def db_session():
    """Sesión SQLite in-memory local (NO la del conftest global) con solo las
    tablas del árbol de las 9 entidades — mismo patrón que
    test_crud001_soft_delete.py / test_cierre_cursada_service.py."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _registrar_regexp_replace(dbapi_connection, connection_record):
        dbapi_connection.create_function("regexp_replace", 3, _regexp_replace_sqlite)

    tablas = [
        Usuario.__table__,
        Materia.__table__,
        CoordinadorMateria.__table__,
        Comision.__table__,
        ComisionTutor.__table__,
        Rubrica.__table__,
        Unidad.__table__,
        ComponenteUnidad.__table__,
        ExamenMateria.__table__,
        Entrega.__table__,
        EntregaHistorial.__table__,
        Correccion.__table__,
        CierreCursadaRun.__table__,
        CierreCursadaAlumno.__table__,
        AvanceSnapshot.__table__,
        AvanceAlumno.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tablas)

    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session

    await engine.dispose()


async def _crear_arbol(db, universidad_id: int, sufijo: str) -> dict:
    """Crea un árbol de datos completo (las 9 entidades) para una universidad."""
    materia = Materia(
        universidad_id=universidad_id,
        codigo=f"PROG{sufijo}",
        nombre=f"Programación {sufijo}",
        activa=True,
    )
    db.add(materia)
    await db.flush()

    comision = Comision(
        universidad_id=universidad_id,
        materia_id=materia.id,
        nombre=f"Comisión {sufijo}",
        anio=2026,
        activa=True,
    )
    db.add(comision)

    rubrica = Rubrica(
        universidad_id=universidad_id,
        materia_id=materia.id,
        tipo=TipoRubricaEnum.TP,
        numero=1,
        anio=2026,
        titulo=f"TP1 {sufijo}",
        descripcion="desc",
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[{"id": "C1", "peso": 100}],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        fuente=FuenteRubricaEnum.MANUAL,
        activa=True,
    )
    db.add(rubrica)

    unidad = Unidad(
        universidad_id=universidad_id,
        materia_id=materia.id,
        numero=1,
        moodle_section_id=100,
        nombre=f"Unidad 1 {sufijo}",
    )
    db.add(unidad)

    examen = ExamenMateria(
        universidad_id=universidad_id,
        materia_id=materia.id,
        tipo=TipoExamenEnum.PARCIAL,
        moodle_cmid=500,
        tipo_actividad=TipoActividadMoodleEnum.ASSIGN,
        modo_aprobacion=ModoAprobacionEnum.NUMERICO,
        nota_minima=60,
        orden=1,
    )
    db.add(examen)

    cierre_run = CierreCursadaRun(
        universidad_id=universidad_id,
        materia_id=materia.id,
        cuatrimestre_id=1,
        generado_por_id=1,
        total_alumnos=0,
    )
    db.add(cierre_run)

    avance_snapshot = AvanceSnapshot(
        universidad_id=universidad_id,
        materia_id=materia.id,
        total_alumnos=0,
    )
    db.add(avance_snapshot)

    await db.flush()

    entrega = Entrega(
        universidad_id=universidad_id,
        comision_id=comision.id,
        rubrica_id=rubrica.id,
        alumno_nombre=f"Alumno {sufijo}",
        archivo_nombre="entrega.zip",
        archivo_tamanio=100,
        archivo_tipo="zip",
        estado=EstadoEntregaEnum.CORREGIDA,
        hash_sha256=f"hash{sufijo}",
        subido_por_id=1,
    )
    db.add(entrega)
    await db.flush()

    correccion = Correccion(
        universidad_id=universidad_id,
        entrega_id=entrega.id,
        nota=Decimal("80.00"),
        criterios_json={"criterios": []},
    )
    db.add(correccion)

    await db.commit()

    return {
        "materia_id": materia.id,
        "comision_id": comision.id,
        "rubrica_id": rubrica.id,
        "unidad_id": unidad.id,
        "examen_id": examen.id,
        "cierre_run_id": cierre_run.id,
        "avance_snapshot_id": avance_snapshot.id,
        "entrega_id": entrega.id,
        "correccion_id": correccion.id,
    }


@pytest_asyncio.fixture
async def dos_universidades(db_session):
    """Dos universidades (UniA=1, UniB=2) con un árbol de datos completo cada una."""
    arbol_a = await _crear_arbol(db_session, UNI_A, "A")
    arbol_b = await _crear_arbol(db_session, UNI_B, "B")
    return {"A": arbol_a, "B": arbol_b}


# ============================================================================
# GATE 1 — listados: UniA no ve NADA de UniB (repository level, el WHERE real)
# ============================================================================


@pytest.mark.asyncio
async def test_materias_de_uniA_no_incluyen_materias_de_uniB(db_session, dos_universidades):
    materias, total = await MateriaRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {m.id for m in materias}
    assert dos_universidades["A"]["materia_id"] in ids
    assert dos_universidades["B"]["materia_id"] not in ids
    assert total == len(materias)  # el count también queda scopeado (no revela el global)


@pytest.mark.asyncio
async def test_comisiones_de_uniA_no_incluyen_comisiones_de_uniB(db_session, dos_universidades):
    comisiones, _ = await ComisionRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {c.id for c in comisiones}
    assert dos_universidades["A"]["comision_id"] in ids
    assert dos_universidades["B"]["comision_id"] not in ids


@pytest.mark.asyncio
async def test_entregas_de_uniA_no_incluyen_entregas_de_uniB(db_session, dos_universidades):
    entregas, _ = await EntregaRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {e.id for e in entregas}
    assert dos_universidades["A"]["entrega_id"] in ids
    assert dos_universidades["B"]["entrega_id"] not in ids


@pytest.mark.asyncio
async def test_correcciones_de_uniA_no_incluyen_correcciones_de_uniB(db_session, dos_universidades):
    correcciones, _ = await CorreccionRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {c.id for c in correcciones}
    assert dos_universidades["A"]["correccion_id"] in ids
    assert dos_universidades["B"]["correccion_id"] not in ids


@pytest.mark.asyncio
async def test_unidades_de_uniA_no_incluyen_unidades_de_uniB(db_session, dos_universidades):
    """Unidad se filtra por materia_id + universidad_id (defensa en profundidad)."""
    repo = UnidadRepository(db_session)
    unidades_a = await repo.get_by_materia(
        dos_universidades["A"]["materia_id"], universidad_id=UNI_A
    )
    unidades_b_con_ctx_a = await repo.get_by_materia(
        dos_universidades["B"]["materia_id"], universidad_id=UNI_A
    )
    assert {u.id for u in unidades_a} == {dos_universidades["A"]["unidad_id"]}
    assert unidades_b_con_ctx_a == []  # materia de UniB pedida con universidad_id de UniA


@pytest.mark.asyncio
async def test_rubricas_de_uniA_no_incluyen_rubricas_de_uniB(db_session, dos_universidades):
    rubricas, _ = await RubricaRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {r.id for r in rubricas}
    assert dos_universidades["A"]["rubrica_id"] in ids
    assert dos_universidades["B"]["rubrica_id"] not in ids


@pytest.mark.asyncio
async def test_examenes_de_uniA_no_incluyen_examenes_de_uniB(db_session, dos_universidades):
    repo = ExamenRepository(db_session)
    examenes_b_con_ctx_a = await repo.get_by_materia(
        dos_universidades["B"]["materia_id"], universidad_id=UNI_A
    )
    examenes_a = await repo.get_by_materia(
        dos_universidades["A"]["materia_id"], universidad_id=UNI_A
    )
    assert examenes_b_con_ctx_a == []
    assert {e.id for e in examenes_a} == {dos_universidades["A"]["examen_id"]}


@pytest.mark.asyncio
async def test_cierre_cursada_runs_de_uniA_no_incluyen_runs_de_uniB(db_session, dos_universidades):
    repo = CierreCursadaRepository(db_session)
    runs_a = await repo.listar_runs(dos_universidades["A"]["materia_id"], universidad_id=UNI_A)
    runs_b_con_ctx_a = await repo.listar_runs(
        dos_universidades["B"]["materia_id"], universidad_id=UNI_A
    )
    assert {r.id for r in runs_a} == {dos_universidades["A"]["cierre_run_id"]}
    assert runs_b_con_ctx_a == []


@pytest.mark.asyncio
async def test_avance_snapshots_de_uniA_no_incluyen_snapshots_de_uniB(db_session, dos_universidades):
    repo = AvanceRepository(db_session)
    materia_ids = [dos_universidades["A"]["materia_id"], dos_universidades["B"]["materia_id"]]
    snapshots = await repo.get_ultimos_snapshots(materia_ids, universidad_id=UNI_A)
    ids = {s.id for s in snapshots}
    assert dos_universidades["A"]["avance_snapshot_id"] in ids
    assert dos_universidades["B"]["avance_snapshot_id"] not in ids


# ============================================================================
# GATE 2 — acceso por id: recurso de UniB pedido con universidad activa UniA
# responde 404 (no 403), a través del service real (repo + verificar_pertenencia)
# ============================================================================


@pytest.mark.asyncio
async def test_obtener_materia_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    with pytest.raises(HTTPException) as exc:
        await MateriaService(db_session).obtener_materia(
            dos_universidades["B"]["materia_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_obtener_comision_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    with pytest.raises(HTTPException) as exc:
        await ComisionService(db_session).obtener_comision(
            dos_universidades["B"]["comision_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_obtener_entrega_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    with pytest.raises(HTTPException) as exc:
        await EntregaService(db_session).obtener_entrega(
            dos_universidades["B"]["entrega_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_obtener_correccion_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    with pytest.raises(HTTPException) as exc:
        await CorreccionService(db_session).obtener_correccion(
            dos_universidades["B"]["correccion_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_obtener_rubrica_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    with pytest.raises(HTTPException) as exc:
        await RubricaService(db_session).obtener_rubrica(
            dos_universidades["B"]["rubrica_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_actualizar_unidad_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    """Unidad no tiene un obtener_* público; el 404 se prueba vía el guard interno
    (_get_unidad_or_404) que comparten todos los métodos por id del service."""
    from app.schemas.unidad import UnidadUpdate

    with pytest.raises(HTTPException) as exc:
        await UnidadService(db_session).actualizar_unidad(
            dos_universidades["B"]["unidad_id"],
            UnidadUpdate(),
            universidad_id=UNI_A,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_actualizar_examen_de_uniB_con_universidad_activa_uniA_da_404(db_session, dos_universidades):
    from app.schemas.examen import ExamenMateriaUpdate

    with pytest.raises(HTTPException) as exc:
        await ExamenService(db_session).actualizar(
            dos_universidades["B"]["examen_id"],
            ExamenMateriaUpdate(
                tipo=TipoExamenEnum.PARCIAL,
                moodle_cmid=1,
                tipo_actividad=TipoActividadMoodleEnum.ASSIGN,
                modo_aprobacion=ModoAprobacionEnum.NUMERICO,
                nota_minima=60,
                recupera_examen_id=None,
            ),
            universidad_id=UNI_A,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_cierre_run_de_uniB_con_universidad_activa_uniA_da_404_en_el_guard(
    db_session, dos_universidades
):
    """cierre_cursada.py aplica `verificar_pertenencia_universidad` directo en el
    router (no hay un `obtener_run` en el service que ya lo encapsule)."""
    run = await CierreCursadaRepository(db_session).get_run(dos_universidades["B"]["cierre_run_id"])
    with pytest.raises(HTTPException) as exc:
        verificar_pertenencia_universidad(run, UNI_A, detail="Corrida no encontrada")
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_avance_snapshot_de_uniB_con_universidad_activa_uniA_no_visible(
    db_session, dos_universidades
):
    """Avance no se accede por id suelto en los routers (siempre vía materia_id
    scopeado): el aislamiento se prueba como ausencia en get_ultimo_snapshot."""
    snap = await AvanceRepository(db_session).get_ultimo_snapshot(
        dos_universidades["B"]["materia_id"], universidad_id=UNI_A
    )
    assert snap is None


# ============================================================================
# GATE 3 — recursos PROPIOS (misma universidad) se acceden con normalidad
# ============================================================================


@pytest.mark.asyncio
async def test_obtener_materia_propia_funciona_normalmente(db_session, dos_universidades):
    resp = await MateriaService(db_session).obtener_materia(
        dos_universidades["A"]["materia_id"], universidad_id=UNI_A
    )
    assert resp.id == dos_universidades["A"]["materia_id"]


@pytest.mark.asyncio
async def test_universidad_b_tampoco_ve_recursos_de_universidad_a(db_session, dos_universidades):
    """Aislamiento simétrico: UniB no ve nada de UniA tampoco."""
    materias, _ = await MateriaRepository(db_session).get_all(universidad_id=UNI_B)
    ids = {m.id for m in materias}
    assert dos_universidades["B"]["materia_id"] in ids
    assert dos_universidades["A"]["materia_id"] not in ids

    with pytest.raises(HTTPException) as exc:
        await MateriaService(db_session).obtener_materia(
            dos_universidades["A"]["materia_id"], universidad_id=UNI_B
        )
    assert exc.value.status_code == 404


# ============================================================================
# GATE 4 — superadmin SIN universidad activa ve AMBAS universidades
# ============================================================================


@pytest.mark.asyncio
async def test_superadmin_sin_universidad_ve_materias_de_ambas_universidades(
    db_session, dos_universidades
):
    materias, total = await MateriaRepository(db_session).get_all(universidad_id=None)
    ids = {m.id for m in materias}
    assert dos_universidades["A"]["materia_id"] in ids
    assert dos_universidades["B"]["materia_id"] in ids
    assert total == len(materias)


@pytest.mark.asyncio
async def test_superadmin_sin_universidad_ve_comisiones_de_ambas(db_session, dos_universidades):
    comisiones, _ = await ComisionRepository(db_session).get_all(universidad_id=None)
    ids = {c.id for c in comisiones}
    assert dos_universidades["A"]["comision_id"] in ids
    assert dos_universidades["B"]["comision_id"] in ids


@pytest.mark.asyncio
async def test_superadmin_sin_universidad_ve_entregas_de_ambas(db_session, dos_universidades):
    entregas, _ = await EntregaRepository(db_session).get_all(universidad_id=None)
    ids = {e.id for e in entregas}
    assert dos_universidades["A"]["entrega_id"] in ids
    assert dos_universidades["B"]["entrega_id"] in ids


@pytest.mark.asyncio
async def test_superadmin_sin_universidad_accede_a_recurso_de_cualquier_universidad(
    db_session, dos_universidades
):
    resp_a = await MateriaService(db_session).obtener_materia(
        dos_universidades["A"]["materia_id"], universidad_id=None
    )
    resp_b = await MateriaService(db_session).obtener_materia(
        dos_universidades["B"]["materia_id"], universidad_id=None
    )
    assert resp_a.id == dos_universidades["A"]["materia_id"]
    assert resp_b.id == dos_universidades["B"]["materia_id"]


# ============================================================================
# GATE 5 — superadmin CON universidad elegida queda scopeado a esa universidad
# ============================================================================


@pytest.mark.asyncio
async def test_superadmin_con_universidad_elegida_solo_ve_esa_universidad(
    db_session, dos_universidades
):
    """D5/OQ2: 'hay universidad_id => filtra', sin rama especial para superadmin."""
    materias, _ = await MateriaRepository(db_session).get_all(universidad_id=UNI_A)
    ids = {m.id for m in materias}
    assert dos_universidades["A"]["materia_id"] in ids
    assert dos_universidades["B"]["materia_id"] not in ids


@pytest.mark.asyncio
async def test_superadmin_con_universidad_elegida_404_en_recurso_de_otra(
    db_session, dos_universidades
):
    with pytest.raises(HTTPException) as exc:
        await MateriaService(db_session).obtener_materia(
            dos_universidades["B"]["materia_id"], universidad_id=UNI_A
        )
    assert exc.value.status_code == 404


# ============================================================================
# GATE 6 — invariante mono-tenant: con UNA sola universidad, nada cambia
# ============================================================================


@pytest.mark.asyncio
async def test_invariante_mono_tenant_una_sola_universidad_ve_todo_lo_suyo(db_session):
    """Con una sola universidad poblada, el filtro no le esconde nada al usuario."""
    arbol = await _crear_arbol(db_session, UNI_A, "SOLO")

    materias, total = await MateriaRepository(db_session).get_all(universidad_id=UNI_A)
    assert total == 1
    assert materias[0].id == arbol["materia_id"]

    resp = await MateriaService(db_session).obtener_materia(
        arbol["materia_id"], universidad_id=UNI_A
    )
    assert resp.id == arbol["materia_id"]
