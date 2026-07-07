"""
Test de exploración de la Bug Condition (bugfix comision-orden-numerico-fix, tarea 1)
y validación del fix (tarea 3.6).

Property 1: Bug Condition / Expected Behavior - Orden numérico natural del nombre de
comisión (design.md).

HISTORIAL (tarea 1): estos tests se ejecutaron originalmente sobre el código SIN
ARREGLAR y FALLARON en las 4 superficies, confirmando que el bug existe (comparación
textual del nombre de comisión en vez de por el valor ENTERO de su sufijo numérico).
Los contraejemplos observados en ese momento están documentados en los docstrings de
cada test (sección "Contraejemplo histórico").

ESTADO ACTUAL (tarea 3.6): una vez aplicado el fix (módulo `app.utils.orden_natural` +
los 4 reemplazos de `order_by`/clave de orden en `_agrupar_por_comision`,
`comision_repository`, `cierre_cursada_repository` y `avance_repository`), este mismo
archivo se re-ejecuta SIN CAMBIOS en la lógica de setup, y TODOS los tests deben pasar
validando el orden numérico natural esperado.

Superficies cubiertas (una causa raíz — comparar el nombre como `str` — replicada 4
veces, ver design.md "Fix Implementation"):
  1. Excel de cierre (`excel_cierre_cursada._agrupar_por_comision`) — puro, sin DB.
  2. Listado de comisiones (`comision_repository.ComisionRepository.get_all`) — SQL.
  3. Corrida de cierre (`cierre_cursada_repository.CierreCursadaRepository.get_alumnos_de_run`) — SQL.
  4. Reporte de avance (`avance_repository.AvanceRepository.get_alumnos_de_snapshot`) — SQL.

**Nota sobre el caso concreto de la Superficie 3 (ajuste respecto de la redacción
literal de la tarea).** La tarea sugiere el par `"M26 C1-02"` / `"M26 C1-10"` (ambos con
sufijo numérico *cero-rellenado a 2 dígitos*, igual longitud de cadena). Verificado
empíricamente: como AMBAS cadenas tienen la MISMA longitud, el orden lexicográfico
actual YA coincide con el natural (`"02" < "10"` carácter a carácter) — ese par
concreto NO dispara el bug (la Bug Condition formal de design.md exige sufijos de
*distinta* longitud de dígitos). Se usa en su lugar `"M26 C1-2"` (1 dígito) vs.
`"M26 C1-10"` (2 dígitos) — mismo prefijo/formato real (`M26 C1-N`, ver
`test_gestion_service.py`), pero con longitudes de sufijo distintas, que sí reproduce
el defecto documentado (comparación textual del nombre completo).

Scoped PBT Approach (tarea 1): casos concretos con sufijos de distinta longitud para
reproducibilidad (superficies 1-4 abajo) + un test property-based con `hypothesis`
sobre listas aleatorias `PREFIJO-<n>` ejercitando la única función pura accesible sin
DB (`_agrupar_por_comision`, superficie 1).

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4**
"""

import re
from datetime import datetime

import pytest
import pytest_asyncio
from hypothesis import given, strategies as st
from sqlalchemy import ARRAY, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from app.models.avance import AvanceAlumno, AvanceSnapshot
from app.models.base import Base
from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun
from app.models.cohorte import Cohorte, Cuatrimestre
from app.models.comision import Comision, ComisionTutor
from app.models.componente_unidad import ComponenteUnidad
from app.models.entrega import Entrega
from app.models.enums import EstadoAvanceEnum, EstadoCierreEnum
from app.models.examen_materia import ExamenMateria
from app.models.materia import CoordinadorMateria, Materia
from app.models.rubrica import Rubrica
from app.models.unidad import Unidad
from app.models.usuario import Usuario
from app.repositories.avance_repository import AvanceRepository
from app.repositories.cierre_cursada_repository import CierreCursadaRepository
from app.repositories.comision_repository import ComisionRepository
from app.services.excel_cierre_cursada import _agrupar_por_comision


# SQLite no tiene JSONB nativo; se compila como JSON (mismo patrón que
# test_cierre_cursada_service.py / test_cierre_cursada.py — sólo afecta al dialecto de
# tests, Postgres sigue usando JSONB real en producción).
@compiles(JSONB, "sqlite")
def _jsonb_como_json_en_sqlite(element, compiler, **kw):
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json_en_sqlite(element, compiler, **kw):
    return "JSON"


def _regexp_replace_sqlite(source: str | None, pattern: str, replacement: str) -> str | None:
    """UDF (user-defined function) que replica, para efectos de este test suite, la
    semántica de `regexp_replace(source, pattern, replacement)` de PostgreSQL que usa
    `orden_natural_sql` (app/utils/orden_natural.py): reemplaza sólo la PRIMERA
    coincidencia del patrón (comportamiento por defecto de Postgres sin la bandera
    'g'), soportando backreferences con sintaxis `\\1` -- la misma que usa
    `re.sub`, por lo que el patrón/reemplazo SQL (`r"^.*?(\\d+)$"`, `r"\\1"`) funciona
    sin traducción.

    NOTA (alcance del shim, no altera producción): SQLite no tiene `regexp_replace`
    nativo; esta función se registra como UDF SOLO en la conexión SQLite en memoria
    usada por los tests (ver `db_session` más abajo), para poder ejecutar el mismo SQL
    que en producción corre contra PostgreSQL real (ver design.md → "Decisión: Python
    vs SQL", tradeoff documentado). `nullif` y `NULLS LAST` son soportados nativamente
    por SQLite (>= 3.30), así que no requieren shim adicional.
    """
    if source is None:
        return None
    return re.sub(pattern, replacement, source, count=1)


@pytest_asyncio.fixture
async def db_session():
    """Sesión SQLite en memoria con SOLO las tablas necesarias para las superficies
    2, 3 y 4 (Comision, CierreCursadaAlumno/Run, AvanceAlumno/Snapshot + sus FKs)."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)

    @event.listens_for(engine.sync_engine, "connect")
    def _registrar_regexp_replace(dbapi_connection, connection_record):
        dbapi_connection.create_function("regexp_replace", 3, _regexp_replace_sqlite)

    tablas = [
        Usuario.__table__,
        Cohorte.__table__,
        Cuatrimestre.__table__,
        Materia.__table__,
        CoordinadorMateria.__table__,
        Unidad.__table__,
        ComponenteUnidad.__table__,
        ExamenMateria.__table__,
        Rubrica.__table__,
        Comision.__table__,
        ComisionTutor.__table__,
        Entrega.__table__,
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


async def _crear_materia(db_session) -> Materia:
    materia = Materia(nombre="Programación 1", codigo="P1")
    db_session.add(materia)
    await db_session.flush()
    return materia


async def _crear_usuario(db_session) -> Usuario:
    usuario = Usuario(
        username="coord1", password_hash="x", nombre="Coordinador",
        rol="ADMIN",
    )
    db_session.add(usuario)
    await db_session.flush()
    return usuario


async def _crear_cuatrimestre(db_session) -> Cuatrimestre:
    cohorte = Cohorte(codigo="M26", nombre="M26")
    db_session.add(cohorte)
    await db_session.flush()
    cuatrimestre = Cuatrimestre(nombre="1C", cohorte_id=cohorte.id, numero=1)
    db_session.add(cuatrimestre)
    await db_session.flush()
    return cuatrimestre


# ============================================================================
# Superficie 1 (Excel) — `_agrupar_por_comision`, sin DB (función pura)
# ============================================================================


def _alumno_cierre(comision_nombre: str, apellido: str = "Ap", nombre: str = "No") -> CierreCursadaAlumno:
    return CierreCursadaAlumno(
        moodle_user_id=1, nombre=nombre, apellido=apellido, email=f"{nombre}@x.com",
        comision_id=None, comision_nombre=comision_nombre, tutor_nombre=None,
        estado=EstadoCierreEnum.PROMOCIONA,
    )


def test_bug_superficie1_excel_bloques_no_quedan_en_orden_natural():
    """`_agrupar_por_comision` con alumnos en COMI-1, COMI-2, COMI-10, COMI-20 ->
    esperado (orden natural) `["COMI-1", "COMI-2", "COMI-10", "COMI-20"]`.

    Contraejemplo histórico (código sin arreglar, tarea 1): ordenaba alfabéticamente
    (`nombre.casefold()`) -> `["COMI-1", "COMI-10", "COMI-2", "COMI-20"]` (COMI-10
    antes de COMI-2), confirmando la Bug Condition. Tras el fix (tarea 3.2, uso de
    `natural_key`), esta aserción valida el comportamiento esperado.
    **Validates: Requirements 1.2, 2.2**"""
    alumnos = [
        _alumno_cierre("COMI-10", "Aa", "Bb"),
        _alumno_cierre("COMI-1", "Cc", "Dd"),
        _alumno_cierre("COMI-20", "Ee", "Ff"),
        _alumno_cierre("COMI-2", "Gg", "Hh"),
    ]

    titulos = list(_agrupar_por_comision(alumnos).keys())

    # Aserción de comportamiento ESPERADO (orden numérico natural).
    assert titulos == ["COMI-1", "COMI-2", "COMI-10", "COMI-20"]


# ============================================================================
# Superficie 2 (Listado) — `ComisionRepository.get_all`, SQL
# ============================================================================


@pytest.mark.asyncio
async def test_bug_superficie2_listado_comi10_antes_de_comi2_mismo_anio(db_session):
    """Comisiones del mismo año `COMI-2` y `COMI-10` -> esperado (orden natural)
    `COMI-2` antes de `COMI-10`.

    Contraejemplo histórico (código sin arreglar, tarea 1): `get_all` ordenaba por
    `Comision.nombre.asc()` (texto) -> `COMI-10` antes de `COMI-2`, confirmando la Bug
    Condition. Tras el fix (tarea 3.3, uso de `orden_natural_sql`), esta aserción
    valida el comportamiento esperado.
    **Validates: Requirements 1.1, 2.1**"""
    materia = await _crear_materia(db_session)
    db_session.add_all([
        Comision(materia_id=materia.id, nombre="COMI-10", anio=2026),
        Comision(materia_id=materia.id, nombre="COMI-2", anio=2026),
    ])
    await db_session.commit()

    repo = ComisionRepository(db_session)
    comisiones, total = await repo.get_all(materia_id=materia.id, anio=2026)

    nombres = [c.nombre for c in comisiones]
    assert total == 2

    # Aserción de comportamiento ESPERADO (orden numérico natural).
    assert nombres == ["COMI-2", "COMI-10"]


# ============================================================================
# Superficie 3 (Corrida de cierre) — `CierreCursadaRepository.get_alumnos_de_run`, SQL
# ============================================================================


@pytest.mark.asyncio
async def test_bug_superficie3_corrida_cierre_comi10_antes_de_comi2(db_session):
    """Alumnos con `comision_nombre` `M26 C1-2` y `M26 C1-10` (sufijos de DISTINTA
    longitud de dígitos — ver nota del módulo sobre el ajuste respecto del par
    zero-padded `M26 C1-02`/`M26 C1-10` sugerido literalmente en la tarea, que NO
    dispara el bug por tener igual longitud de cadena) -> esperado (orden natural)
    `M26 C1-2` antes de `M26 C1-10`.

    Contraejemplo histórico (código sin arreglar, tarea 1): `get_alumnos_de_run`
    ordenaba por `comision_nombre.asc().nullslast()` (texto) -> `M26 C1-10` antes de
    `M26 C1-2`, confirmando la Bug Condition. Tras el fix (tarea 3.4, uso de
    `orden_natural_sql`), esta aserción valida el comportamiento esperado.
    **Validates: Requirements 1.3, 2.3**"""
    materia = await _crear_materia(db_session)
    cuatrimestre = await _crear_cuatrimestre(db_session)
    usuario = await _crear_usuario(db_session)

    run = CierreCursadaRun(
        materia_id=materia.id, cuatrimestre_id=cuatrimestre.id,
        generado_por_id=usuario.id, total_alumnos=2,
    )
    run.alumnos = [
        _alumno_cierre("M26 C1-10", "Aa", "Bb"),
        _alumno_cierre("M26 C1-2", "Cc", "Dd"),
    ]
    db_session.add(run)
    await db_session.commit()

    repo = CierreCursadaRepository(db_session)
    alumnos = await repo.get_alumnos_de_run(run.id)

    nombres = [a.comision_nombre for a in alumnos]

    # Aserción de comportamiento ESPERADO (orden numérico natural).
    assert nombres == ["M26 C1-2", "M26 C1-10"]


# ============================================================================
# Superficie 4 (Avance) — `AvanceRepository.get_alumnos_de_snapshot`, SQL
# ============================================================================


def _alumno_avance(comision: str, apellido: str = "Ap", nombre: str = "No") -> AvanceAlumno:
    return AvanceAlumno(
        moodle_user_id=1, nombre=nombre, apellido=apellido, email=f"{nombre}@x.com",
        comision=comision, estado=EstadoAvanceEnum.AL_DIA,
    )


@pytest.mark.asyncio
async def test_bug_superficie4_avance_comi21_antes_de_comi3(db_session):
    """`AvanceAlumno.comision` `COMI-3` y `COMI-21` -> esperado (orden natural)
    `COMI-3` antes de `COMI-21`.

    Contraejemplo histórico (código sin arreglar, tarea 1): `get_alumnos_de_snapshot`
    ordenaba por `comision.asc().nullslast()` (texto) -> `COMI-21` antes de `COMI-3`,
    confirmando la Bug Condition. Tras el fix (tarea 3.5, uso de `orden_natural_sql`),
    esta aserción valida el comportamiento esperado.
    **Validates: Requirements 1.4, 2.4**"""
    materia = await _crear_materia(db_session)
    snapshot = AvanceSnapshot(materia_id=materia.id, total_alumnos=2)
    snapshot.alumnos = [
        _alumno_avance("COMI-21", "Aa", "Bb"),
        _alumno_avance("COMI-3", "Cc", "Dd"),
    ]
    db_session.add(snapshot)
    await db_session.commit()

    repo = AvanceRepository(db_session)
    alumnos = await repo.get_alumnos_de_snapshot(snapshot.id)

    nombres = [a.comision for a in alumnos]

    # Aserción de comportamiento ESPERADO (orden numérico natural).
    assert nombres == ["COMI-3", "COMI-21"]


# ============================================================================
# Complemento property-based (hypothesis): listas aleatorias `PREFIJO-<n>`
# ============================================================================
#
# Ejercita la única función pura accesible sin DB (`_agrupar_por_comision`,
# superficie 1) con nombres `PREFIJO-<n>` generados al azar. Cuando el conjunto
# dispara la Bug Condition (isBugCondition, design.md — el orden lexicográfico
# difiere del natural), el orden HOY observado (`_agrupar_por_comision` sin arreglar)
# NO puede coincidir con el orden numérico natural esperado. Falla en cuanto
# hypothesis encuentra un contraejemplo con sufijos de distinta longitud.
# **Validates: Requirements 1.2, 2.2**

_PREFIJOS = ["COMI", "A27", "M26"]


def _es_bug_condition(nombres: list[str]) -> bool:
    """Replica `isBugCondition` de design.md: el orden lexicográfico difiere del
    natural (por el valor entero del sufijo numérico)."""
    orden_textual = sorted(nombres, key=str.casefold)
    orden_natural = sorted(nombres, key=lambda n: (n.rsplit("-", 1)[0].casefold(), int(n.rsplit("-", 1)[1])))
    return orden_textual != orden_natural


@given(
    prefijo=st.sampled_from(_PREFIJOS),
    numeros=st.lists(st.integers(min_value=0, max_value=999), min_size=2, max_size=8, unique=True),
)
def test_prop1_bug_random_prefijo_n_orden_natural_no_coincide_con_actual(prefijo, numeros):
    nombres = [f"{prefijo}-{n}" for n in numeros]
    if not _es_bug_condition(nombres):
        return  # este conjunto concreto no dispara el bug (todos mismo largo de dígitos)

    alumnos = [_alumno_cierre(nombre, f"Ap{i}", f"No{i}") for i, nombre in enumerate(nombres)]
    titulos_actuales = list(_agrupar_por_comision(alumnos).keys())

    orden_natural_esperado = sorted(
        nombres, key=lambda n: (n.rsplit("-", 1)[0].casefold(), int(n.rsplit("-", 1)[1]))
    )

    # DEBE FALLAR sobre el código sin arreglar: hoy `_agrupar_por_comision` ordena
    # alfabéticamente (casefold), no por el valor entero del sufijo.
    assert titulos_actuales == orden_natural_esperado
