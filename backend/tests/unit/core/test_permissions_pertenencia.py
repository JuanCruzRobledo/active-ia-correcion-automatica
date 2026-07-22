"""
Tests de los guards de pertenencia combinados (SEC-001 / SEC-002 / SEC-004).

Cubre la UNION de los dos ejes de pertenencia que hoy viven sueltos y son
mutuamente excluyentes (`verificar_acceso_comision` mira solo ComisionTutor,
`verificar_acceso_materia_de_comision` mira solo CoordinadorMateria):

- ADMIN: pasa sin consultar la DB.
- TUTOR asignado a la comision: pasa.
- COORDINADOR de la materia de esa comision: pasa.
- GESTOR y cualquier otro: 403.
- Recurso inexistente: 404 (en los guards de recurso unico).

Los guards de lote NO distinguen "no existe" de "no tenes acceso": ambos caen
en denegados, a proposito, para no convertir el endpoint en un oraculo de
enumeracion de IDs.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.core.permissions import (
    comisiones_visibles_para,
    filtrar_entregas_accesibles,
    verificar_acceso_comision_o_materia,
    verificar_acceso_correccion,
    verificar_acceso_entrega,
)
from app.models.enums import RolEnum

ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)
TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR)
COORD = SimpleNamespace(id=7, rol=RolEnum.COORDINADOR)
GESTOR = SimpleNamespace(id=9, rol=RolEnum.GESTOR)


def _db_first(*rows):
    """db async cuyo execute().first() devuelve rows[i] en la i-esima llamada."""
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


def _db_scalars(*listas):
    """db async cuyo execute().scalars().all() devuelve listas[i] en la i-esima llamada."""
    db = AsyncMock()
    resultados = []
    for lista in listas:
        res = MagicMock()
        res.scalars.return_value.all.return_value = list(lista)
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# Filas del LEFT JOIN de verificar_acceso_comision_o_materia:
# (comision_id, comision_tutor_id, coordinador_materia_id)
_COMISION_INEXISTENTE = None
_SIN_PERTENENCIA = (10, None, None)
_ES_TUTOR = (10, 555, None)
_ES_COORDINADOR = (10, None, 777)


# ===================== verificar_acceso_comision_o_materia =====================


@pytest.mark.asyncio
async def test_comision_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_comision_o_materia(db, ADMIN, 99)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_comision_tutor_asignado_ok():
    db = _db_first(_ES_TUTOR)
    await verificar_acceso_comision_o_materia(db, TUTOR, 10)  # no lanza


@pytest.mark.asyncio
async def test_comision_tutor_ajeno_403():
    db = _db_first(_SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_comision_o_materia(db, TUTOR, 10)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_comision_coordinador_de_la_materia_ok():
    """El eje que hoy falta: coordinador entra aunque no sea tutor de la comision."""
    db = _db_first(_ES_COORDINADOR)
    await verificar_acceso_comision_o_materia(db, COORD, 10)  # no lanza


@pytest.mark.asyncio
async def test_comision_coordinador_de_otra_materia_403():
    db = _db_first(_SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_comision_o_materia(db, COORD, 10)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_comision_gestor_403():
    """GESTOR es rol de reportes de Moodle: no toca el flujo de correccion."""
    db = _db_first(_SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_comision_o_materia(db, GESTOR, 10)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_comision_inexistente_404():
    db = _db_first(_COMISION_INEXISTENTE)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_comision_o_materia(db, TUTOR, 404404)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_comision_resuelve_pertenencia_en_una_sola_query():
    """La union de los dos ejes NO debe costar dos round-trips."""
    db = _db_first(_ES_COORDINADOR)
    await verificar_acceso_comision_o_materia(db, COORD, 10)
    assert db.execute.call_count == 1


# ===================== verificar_acceso_entrega =====================


@pytest.mark.asyncio
async def test_entrega_propia_ok():
    # 1a query: entrega -> comision_id 10. 2a query: pertenencia -> es tutor.
    db = _db_first((42, 10), _ES_TUTOR)
    await verificar_acceso_entrega(db, TUTOR, 42)  # no lanza


@pytest.mark.asyncio
async def test_entrega_ajena_403():
    db = _db_first((42, 10), _SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_entrega(db, TUTOR, 42)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_entrega_inexistente_404():
    db = _db_first(None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_entrega(db, TUTOR, 404404)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_entrega_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_entrega(db, ADMIN, 42)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_entrega_no_selecciona_columnas_deferred():
    """
    contenido_consolidado y pdf_contenido_b64 son deferred=True (PERF-002/006).

    Un guard que hiciera select(Entrega) las arrastraria en CADA verificacion
    de permisos: el codigo fuente completo del alumno, en cada request.
    """
    db = _db_first((42, 10), _ES_TUTOR)
    await verificar_acceso_entrega(db, TUTOR, 42)

    query_compilada = str(db.execute.call_args_list[0].args[0])
    assert "contenido_consolidado" not in query_compilada
    assert "pdf_contenido_b64" not in query_compilada


# ===================== verificar_acceso_correccion =====================


@pytest.mark.asyncio
async def test_correccion_propia_ok():
    # 1a query: correccion -> join entrega -> comision_id 10. 2a: pertenencia.
    db = _db_first((99, 10), _ES_COORDINADOR)
    await verificar_acceso_correccion(db, COORD, 99)  # no lanza


@pytest.mark.asyncio
async def test_correccion_ajena_403():
    db = _db_first((99, 10), _SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_correccion(db, TUTOR, 99)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_correccion_inexistente_404():
    db = _db_first(None)
    with pytest.raises(HTTPException) as exc:
        await verificar_acceso_correccion(db, TUTOR, 404404)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_correccion_admin_pasa_sin_consultar_db():
    db = AsyncMock()
    await verificar_acceso_correccion(db, ADMIN, 99)
    db.execute.assert_not_called()


# ===================== filtrar_entregas_accesibles (lotes) =====================


@pytest.mark.asyncio
async def test_lote_mixto_particiona_permitidos_y_denegados():
    db = _db_scalars([1, 2])  # solo 1 y 2 son accesibles
    permitidos, denegados = await filtrar_entregas_accesibles(db, TUTOR, [1, 2, 3, 4])
    assert permitidos == {1, 2}
    assert denegados == {3, 4}


@pytest.mark.asyncio
async def test_lote_admin_recibe_todo_sin_consultar_db():
    db = AsyncMock()
    permitidos, denegados = await filtrar_entregas_accesibles(db, ADMIN, [1, 2, 3])
    assert permitidos == {1, 2, 3}
    assert denegados == set()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_lote_ids_inexistentes_caen_en_denegados():
    """Deliberado: no distinguir 404 de 403 evita el oraculo de enumeracion."""
    db = _db_scalars([1])
    permitidos, denegados = await filtrar_entregas_accesibles(db, TUTOR, [1, 999999])
    assert permitidos == {1}
    assert denegados == {999999}


@pytest.mark.asyncio
async def test_lote_sin_ninguno_accesible_devuelve_permitidos_vacio():
    db = _db_scalars([])
    permitidos, denegados = await filtrar_entregas_accesibles(db, TUTOR, [1, 2, 3])
    assert permitidos == set()
    assert denegados == {1, 2, 3}


@pytest.mark.asyncio
async def test_lote_lista_vacia_no_consulta_db():
    db = AsyncMock()
    permitidos, denegados = await filtrar_entregas_accesibles(db, TUTOR, [])
    assert permitidos == set()
    assert denegados == set()
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_lote_de_100_ids_ejecuta_exactamente_una_query():
    """Anti N+1: el lote se resuelve con un IN, no con un guard por ID."""
    ids = list(range(1, 101))
    db = _db_scalars(ids)
    permitidos, _ = await filtrar_entregas_accesibles(db, TUTOR, ids)
    assert permitidos == set(ids)
    assert db.execute.call_count == 1


@pytest.mark.asyncio
async def test_lote_no_selecciona_columnas_deferred():
    ids = [1, 2, 3]
    db = _db_scalars(ids)
    await filtrar_entregas_accesibles(db, TUTOR, ids)

    query_compilada = str(db.execute.call_args_list[0].args[0])
    assert "contenido_consolidado" not in query_compilada
    assert "pdf_contenido_b64" not in query_compilada


# ===================== comisiones_visibles_para (scoping del listado) =====================


@pytest.mark.asyncio
async def test_scoping_admin_devuelve_none_sin_consultar_db():
    """None = sin filtro. El admin ve todo."""
    db = AsyncMock()
    assert await comisiones_visibles_para(db, ADMIN) is None
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_scoping_tutor_devuelve_sus_comisiones():
    db = _db_scalars([10, 11])
    assert await comisiones_visibles_para(db, TUTOR) == [10, 11]


@pytest.mark.asyncio
async def test_scoping_coordinador_devuelve_comisiones_de_sus_materias():
    db = _db_scalars([20, 21, 22])
    assert await comisiones_visibles_para(db, COORD) == [20, 21, 22]


@pytest.mark.asyncio
async def test_scoping_gestor_no_ve_ninguna_comision():
    db = _db_scalars([])
    assert await comisiones_visibles_para(db, GESTOR) == []


@pytest.mark.asyncio
async def test_scoping_resuelve_ambos_ejes_en_una_sola_query():
    db = _db_scalars([10, 20])
    await comisiones_visibles_para(db, COORD)
    assert db.execute.call_count == 1
