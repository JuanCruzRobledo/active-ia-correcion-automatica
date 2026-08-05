"""
CRUD-001 (Fase 2): soft delete de entregas en el EntregaRepository.

Cubre los metodos nuevos (soft_delete / restore / soft_delete_by_ids) y, sobre
todo, que TODAS las queries de lectura excluyan las entregas borradas por
defecto. Un olvido de filtro en una sola query = una entrega "borrada" que sigue
apareciendo por ese camino (el mismo tipo de puerta trasera del Excel en SEC-002).
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

UNIV_ID = 1  # multi-tenant-scoping-queries: universidad_id ahora NOT NULL



@compiles(JSONB, "sqlite")
def _jsonb_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


@compiles(ARRAY, "sqlite")
def _array_como_json(element, compiler, **kw):  # noqa: D401
    return "JSON"


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    tablas = [
        Usuario.__table__, Materia.__table__, Comision.__table__,
        ComisionTutor.__table__, Rubrica.__table__, Entrega.__table__,
        EntregaHistorial.__table__, Correccion.__table__,
    ]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tablas)
    session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


_contador_alumno = 0


async def _mk_entrega(db, comi_id=1, *, archivado=False, deleted=False) -> Entrega:
    global _contador_alumno
    _contador_alumno += 1
    e = Entrega(universidad_id=UNIV_ID, 
        comision_id=comi_id,
        rubrica_id=1,
        # nombre unico: hay un unique (rubrica_id, alumno_nombre) en la tabla.
        alumno_nombre=f"Alumno {_contador_alumno}",
        archivo_nombre="tp.zip",
        archivo_tipo="zip",
        estado=EstadoEntregaEnum.SUBIDA,
        archivado=archivado,
        deleted_at=datetime(2026, 6, 1, 12, 0, 0) if deleted else None,
    )
    db.add(e)
    await db.flush()
    return e


async def _seed_comision(db) -> int:
    materia = Materia(universidad_id=UNIV_ID, nombre="Prog 1", codigo="P1")
    db.add(materia)
    await db.flush()
    comi = Comision(universidad_id=UNIV_ID, materia_id=materia.id, nombre="C1", anio=2026, activa=True)
    db.add(comi)
    await db.flush()
    return comi.id


# ===================== soft_delete / restore =====================


@pytest.mark.asyncio
async def test_soft_delete_setea_deleted_at(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert e.deleted_at is None
    await repo.soft_delete(e)
    assert e.deleted_at is not None
    assert e.is_deleted is True


@pytest.mark.asyncio
async def test_restore_pone_deleted_at_en_none(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert e.is_deleted is True
    await repo.restore(e)
    assert e.deleted_at is None
    assert e.is_deleted is False


@pytest.mark.asyncio
async def test_soft_delete_by_ids_marca_solo_los_dados(db_session):
    comi = await _seed_comision(db_session)
    e1 = await _mk_entrega(db_session, comi)
    e2 = await _mk_entrega(db_session, comi)
    e3 = await _mk_entrega(db_session, comi)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    count = await repo.soft_delete_by_ids([e1.id, e3.id])
    assert count == 2
    await db_session.refresh(e1)
    await db_session.refresh(e2)
    await db_session.refresh(e3)
    assert e1.is_deleted and e3.is_deleted
    assert not e2.is_deleted  # e2 no estaba en la lista


# ===================== get_all excluye borradas =====================


@pytest.mark.asyncio
async def test_get_all_excluye_borradas(db_session):
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi)                 # viva
    await _mk_entrega(db_session, comi)                 # viva
    await _mk_entrega(db_session, comi, deleted=True)   # borrada
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all()
    # El total y las filas deben coincidir y NO contar la borrada (aislamiento
    # del count, mismo principio que SEC-002).
    assert total == 2
    assert len(entregas) == 2
    assert all(not e.is_deleted for e in entregas)


@pytest.mark.asyncio
async def test_get_all_count_no_cuenta_borradas(db_session):
    comi = await _seed_comision(db_session)
    for _ in range(3):
        await _mk_entrega(db_session, comi)
    for _ in range(2):
        await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    _, total = await repo.get_all()
    assert total == 3  # las 2 borradas no cuentan en el total paginado


# ===================== get_by_id: excluye por defecto, include_deleted opt-in ===


@pytest.mark.asyncio
async def test_get_by_id_excluye_borrada_por_defecto(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert await repo.get_by_id(e.id) is None  # borrada => no encontrada


@pytest.mark.asyncio
async def test_get_by_id_include_deleted_la_ve(db_session):
    """El restore necesita ver la entrega borrada para poder restaurarla."""
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    encontrada = await repo.get_by_id(e.id, include_deleted=True)
    assert encontrada is not None
    assert encontrada.id == e.id


@pytest.mark.asyncio
async def test_get_by_id_viva_se_ve_normal(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert (await repo.get_by_id(e.id)) is not None


@pytest.mark.asyncio
async def test_get_by_id_with_relations_excluye_borrada(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert await repo.get_by_id_with_relations(e.id) is None


# ===================== ortogonalidad archivado vs deleted_at =====================


@pytest.mark.asyncio
async def test_archivada_no_borrada_sigue_su_propio_filtro(db_session):
    """archivado y deleted_at son ORTOGONALES: archivar no es borrar."""
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi, archivado=True)   # archivada, viva
    await db_session.commit()
    repo = EntregaRepository(db_session)

    # Por defecto get_all excluye archivadas -> 0.
    _, total_default = await repo.get_all()
    assert total_default == 0
    # Pidiendo archivadas, aparece (NO fue borrada).
    entregas, total_arch = await repo.get_all(include_archivadas=True)
    assert total_arch == 1
    assert not entregas[0].is_deleted


@pytest.mark.asyncio
async def test_borrada_y_archivada_nunca_aparece(db_session):
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi, archivado=True, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    # Ni pidiendo archivadas: el borrado gana siempre.
    _, total = await repo.get_all(include_archivadas=True)
    assert total == 0


# ===================== get_all_for_export hereda el filtro =====================


@pytest.mark.asyncio
async def test_export_no_incluye_borradas(db_session):
    """
    get_all_for_export (el Excel de notas) reutiliza get_all internamente, así
    que hereda el filtro de borradas. Se verifica, NO se asume (lección de la
    puerta trasera del Excel en SEC-002).
    """
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi)                 # viva
    await _mk_entrega(db_session, comi, deleted=True)   # borrada
    await db_session.commit()
    repo = EntregaRepository(db_session)

    todas = await repo.get_all_for_export()
    assert len(todas) == 1
    assert all(not e.is_deleted for e in todas)


# ============ lookup por (rubrica, alumno): el que bloqueaba al alumno ============
#
# Estas dos queries son las que deciden si el alta de una entrega tira 409. Si no
# excluyen las borradas, una entrega eliminada deja al alumno sin poder volver a
# entregar: el 409 la ve, pero el listado no, así que no hay forma de encontrarla
# ni de restaurarla. Es el hueco que el docstring de arriba prometía cubrir.


@pytest.mark.asyncio
async def test_get_by_rubrica_alumno_ignora_las_borradas(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert await repo.get_by_rubrica_alumno(e.rubrica_id, e.alumno_nombre) is None


@pytest.mark.asyncio
async def test_get_by_rubrica_alumno_si_devuelve_la_viva(db_session):
    """Triangulación: el filtro no debe tapar las entregas vigentes."""
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    hallada = await repo.get_by_rubrica_alumno(e.rubrica_id, e.alumno_nombre)
    assert hallada is not None
    assert hallada.id == e.id


@pytest.mark.asyncio
async def test_get_by_rubrica_alumno_ignora_borradas_con_load_contenido(db_session):
    """La rama de sobrescritura (load_contenido=True) usa la misma query."""
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    hallada = await repo.get_by_rubrica_alumno(
        e.rubrica_id, e.alumno_nombre, load_contenido=True
    )
    assert hallada is None


@pytest.mark.asyncio
async def test_get_by_rubrica_alumno_ignora_borradas_con_universidad(db_session):
    """El filtro de borradas convive con el scoping multi-tenant."""
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    hallada = await repo.get_by_rubrica_alumno(
        e.rubrica_id, e.alumno_nombre, universidad_id=UNIV_ID
    )
    assert hallada is None


@pytest.mark.asyncio
async def test_exists_by_rubrica_alumno_ignora_las_borradas(db_session):
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert await repo.exists_by_rubrica_alumno(e.rubrica_id, e.alumno_nombre) is False


@pytest.mark.asyncio
async def test_exists_by_rubrica_alumno_si_ve_la_viva(db_session):
    """Triangulación."""
    comi = await _seed_comision(db_session)
    e = await _mk_entrega(db_session, comi)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    assert await repo.exists_by_rubrica_alumno(e.rubrica_id, e.alumno_nombre) is True


# ===================== papelera: ver las eliminadas a pedido =====================
#
# El filtro de borradas es incondicional, así que una entrega eliminada es
# invisible por API y nadie puede saber su id para restaurarla. Estos flags son
# la puerta de salida, con la misma forma que el par include/solo_archivadas.


@pytest.mark.asyncio
async def test_get_all_incluir_eliminadas_trae_vivas_y_borradas(db_session):
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi)
    await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all(incluir_eliminadas=True)
    assert total == 2
    assert len(entregas) == 2
    assert {e.is_deleted for e in entregas} == {True, False}


@pytest.mark.asyncio
async def test_get_all_solo_eliminadas_trae_unicamente_las_borradas(db_session):
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi)
    borrada = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all(solo_eliminadas=True)
    assert total == 1
    assert [e.id for e in entregas] == [borrada.id]


@pytest.mark.asyncio
async def test_get_all_solo_eliminadas_manda_sobre_incluir(db_session):
    """Mismo precedente que solo_archivadas sobre include_archivadas."""
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi)
    borrada = await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all(incluir_eliminadas=True, solo_eliminadas=True)
    assert total == 1
    assert [e.id for e in entregas] == [borrada.id]


@pytest.mark.asyncio
async def test_get_all_por_defecto_sigue_ocultando_las_borradas(db_session):
    """Triangulación: el default no cambia. La papelera es opt-in."""
    comi = await _seed_comision(db_session)
    viva = await _mk_entrega(db_session, comi)
    await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all()
    assert total == 1
    assert [e.id for e in entregas] == [viva.id]


@pytest.mark.asyncio
async def test_papelera_respeta_el_scoping_por_comision(db_session):
    """La papelera no puede ser una puerta trasera al scoping (lección SEC-002)."""
    comi = await _seed_comision(db_session)
    await _mk_entrega(db_session, comi, deleted=True)
    await db_session.commit()
    repo = EntregaRepository(db_session)

    entregas, total = await repo.get_all(solo_eliminadas=True, comisiones_visibles=[])
    assert total == 0
    assert entregas == []
