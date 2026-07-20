"""
Tests de autorizacion por pertenencia en el router de correcciones (SEC-001).

Antes de este change los 6 endpoints usaban SOLO `require_any_authenticated`
(= return user): cualquier usuario podia leer datos de alumnos de otras
comisiones, ALTERAR notas ajenas (PUT), y borrar/regenerar correcciones ajenas.

Cubre los 5 endpoints de recurso unico. El de lote (`POST /lote`) va aparte
por tener que particionar ANTES del background task.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.routers.correcciones import (
    corregir_entrega,
    editar_correccion,
    obtener_correccion,
    obtener_correccion_por_entrega,
    recorregir_entrega,
)

# Usuarios CON api key configurada, para que el happy-path llegue al service
# (el guard de pertenencia corre ANTES de resolver credenciales).
ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN, correction_provider="gemini",
                        gemini_api_key_encrypted="k", openrouter_api_key_encrypted=None)
TUTOR = SimpleNamespace(id=5, rol=RolEnum.TUTOR, correction_provider="gemini",
                        gemini_api_key_encrypted="k", openrouter_api_key_encrypted=None)
COORD = SimpleNamespace(id=7, rol=RolEnum.COORDINADOR, correction_provider="gemini",
                        gemini_api_key_encrypted="k", openrouter_api_key_encrypted=None)
# Tutor ajeno SIN key: si el guard corre primero, recibe 403 (no 400 por falta de key).
TUTOR_SIN_KEY = SimpleNamespace(id=6, rol=RolEnum.TUTOR, correction_provider="gemini",
                                gemini_api_key_encrypted=None, openrouter_api_key_encrypted=None)

_ES_TUTOR = (10, 555, None)
_ES_COORDINADOR = (10, None, 777)
_SIN_PERTENENCIA = (10, None, None)
_ENTREGA_42 = (42, 10)       # (entrega_id, comision_id)
_CORRECCION_99 = (99, 10)    # (correccion_id, comision_id)


def _db(*rows):
    db = AsyncMock()
    resultados = []
    for r in rows:
        res = MagicMock()
        res.first.return_value = r
        resultados.append(res)
    db.execute.side_effect = resultados
    return db


# ===================== POST /entregas/{id}/corregir =====================


@pytest.mark.asyncio
async def test_corregir_entrega_propia_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.corregir_individual = AsyncMock(return_value="CORR")
        assert await corregir_entrega(42, current_user=TUTOR, db=db) == "CORR"


@pytest.mark.asyncio
async def test_corregir_entrega_ajena_403_sin_gastar_llm():
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await corregir_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.corregir_individual.assert_not_called()


@pytest.mark.asyncio
async def test_corregir_entrega_ajena_da_403_antes_que_400_por_falta_de_key():
    """El guard corre ANTES de resolver credenciales: sin acceso, ni se mira la key."""
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await corregir_entrega(42, current_user=TUTOR_SIN_KEY, db=db)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_corregir_entrega_coordinador_de_la_materia_ok():
    db = _db(_ENTREGA_42, _ES_COORDINADOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.corregir_individual = AsyncMock(return_value="CORR")
        assert await corregir_entrega(42, current_user=COORD, db=db) == "CORR"


@pytest.mark.asyncio
async def test_corregir_entrega_inexistente_404():
    db = _db(None)
    with pytest.raises(HTTPException) as exc:
        await corregir_entrega(404404, current_user=TUTOR, db=db)
    assert exc.value.status_code == 404


# ===================== POST /entregas/{id}/recorregir =====================


@pytest.mark.asyncio
async def test_recorregir_entrega_propia_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.recorregir = AsyncMock(return_value="CORR")
        assert await recorregir_entrega(42, current_user=TUTOR, db=db) == "CORR"


@pytest.mark.asyncio
async def test_recorregir_entrega_ajena_403_no_destruye_la_correccion_ajena():
    """recorregir hace hard-delete de la correccion existente: el service NO debe correr."""
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await recorregir_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.recorregir.assert_not_called()


@pytest.mark.asyncio
async def test_recorregir_entrega_admin_ok_sin_consultar_permisos():
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.recorregir = AsyncMock(return_value="CORR")
        assert await recorregir_entrega(42, current_user=ADMIN, db=db) == "CORR"
    db.execute.assert_not_called()


# ===================== GET /correcciones/{id} =====================


@pytest.mark.asyncio
async def test_obtener_correccion_propia_ok():
    db = _db(_CORRECCION_99, _ES_COORDINADOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.obtener_correccion = AsyncMock(return_value="CORR")
        assert await obtener_correccion(99, current_user=COORD, db=db) == "CORR"


@pytest.mark.asyncio
async def test_obtener_correccion_ajena_403():
    db = _db(_CORRECCION_99, _SIN_PERTENENCIA)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await obtener_correccion(99, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.obtener_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_obtener_correccion_inexistente_404():
    db = _db(None)
    with pytest.raises(HTTPException) as exc:
        await obtener_correccion(404404, current_user=TUTOR, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_obtener_correccion_gestor_403():
    db = _db(_CORRECCION_99, _SIN_PERTENENCIA)
    with pytest.raises(HTTPException) as exc:
        await obtener_correccion(99, current_user=SimpleNamespace(id=9, rol=RolEnum.GESTOR), db=db)
    assert exc.value.status_code == 403


# ===================== GET /correcciones/entregas/{id} =====================


@pytest.mark.asyncio
async def test_obtener_correccion_por_entrega_propia_ok():
    db = _db(_ENTREGA_42, _ES_TUTOR)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.obtener_por_entrega = AsyncMock(return_value="CORR")
        assert await obtener_correccion_por_entrega(42, current_user=TUTOR, db=db) == "CORR"


@pytest.mark.asyncio
async def test_obtener_correccion_por_entrega_ajena_403():
    db = _db(_ENTREGA_42, _SIN_PERTENENCIA)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await obtener_correccion_por_entrega(42, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.obtener_por_entrega.assert_not_called()


# ===================== PUT /correcciones/{id} =====================


@pytest.mark.asyncio
async def test_editar_correccion_propia_ok():
    db = _db(_CORRECCION_99, _ES_TUTOR)
    data = SimpleNamespace(nota=80)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.editar_correccion = AsyncMock(return_value="CORR")
        assert await editar_correccion(99, data, current_user=TUTOR, db=db) == "CORR"


@pytest.mark.asyncio
async def test_editar_correccion_ajena_403_no_puede_cambiar_la_nota():
    """El caso mas grave de SEC-001: alterar la NOTA de una correccion ajena."""
    db = _db(_CORRECCION_99, _SIN_PERTENENCIA)
    data = SimpleNamespace(nota=100)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        with pytest.raises(HTTPException) as exc:
            await editar_correccion(99, data, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.editar_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_editar_correccion_coordinador_de_la_materia_ok():
    db = _db(_CORRECCION_99, _ES_COORDINADOR)
    data = SimpleNamespace(nota=75)
    with patch("app.routers.correcciones.CorreccionService") as MockSvc:
        MockSvc.return_value.editar_correccion = AsyncMock(return_value="CORR")
        assert await editar_correccion(99, data, current_user=COORD, db=db) == "CORR"


# ===================== POST /correcciones/lote (particion ANTES del bg task) ====

from app.routers.correcciones import corregir_lote  # noqa: E402
from app.schemas.correccion import CorregirLoteAceptadoResponse  # noqa: E402


class _BgTasks:
    """BackgroundTasks fake que captura add_task."""

    def __init__(self):
        self.llamadas = []

    def add_task(self, func, **kwargs):
        self.llamadas.append(kwargs)


async def _lote(current_user, db, ids):
    bg = _BgTasks()
    data = SimpleNamespace(entrega_ids=ids)
    res = await corregir_lote(data, bg, current_user=current_user, db=db)
    return res, bg


@pytest.mark.asyncio
async def test_lote_mixto_encola_solo_permitidos_e_informa_omitidos():
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc, patch(
        "app.routers.correcciones.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, {3, 4})),
    ):
        MockSvc.return_value.encolar_lote = AsyncMock(return_value=[1, 2])
        res, bg = await _lote(TUTOR, db, [1, 2, 3, 4])
    assert res.total_encoladas == 2
    assert res.omitidas == 2
    assert res.entrega_ids_omitidos == [3, 4]


@pytest.mark.asyncio
async def test_lote_el_background_task_recibe_solo_permitidos():
    """El corazon de la sub-fase: el bg task no tiene usuario para re-validar."""
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc, patch(
        "app.routers.correcciones.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, {99})),
    ):
        MockSvc.return_value.encolar_lote = AsyncMock(return_value=[1, 2])
        _, bg = await _lote(TUTOR, db, [1, 2, 99])
    assert len(bg.llamadas) == 1
    assert bg.llamadas[0]["entrega_ids"] == [1, 2]
    assert 99 not in bg.llamadas[0]["entrega_ids"]


@pytest.mark.asyncio
async def test_lote_encolar_recibe_solo_permitidos_ordenados():
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc, patch(
        "app.routers.correcciones.filtrar_entregas_accesibles",
        AsyncMock(return_value=({2, 1}, {3})),
    ):
        MockSvc.return_value.encolar_lote = AsyncMock(return_value=[1, 2])
        await _lote(TUTOR, db, [1, 2, 3])
        req = MockSvc.return_value.encolar_lote.await_args.args[0]
    assert list(req.entrega_ids) == [1, 2]


@pytest.mark.asyncio
async def test_lote_todo_denegado_403_no_encola_ni_agenda_nada():
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc, patch(
        "app.routers.correcciones.filtrar_entregas_accesibles",
        AsyncMock(return_value=(set(), {3, 4})),
    ):
        bg = _BgTasks()
        data = SimpleNamespace(entrega_ids=[3, 4])
        with pytest.raises(HTTPException) as exc:
            await corregir_lote(data, bg, current_user=TUTOR, db=db)
    assert exc.value.status_code == 403
    MockSvc.return_value.encolar_lote.assert_not_called()
    assert bg.llamadas == []


@pytest.mark.asyncio
async def test_lote_todo_propio_no_reporta_omitidos():
    db = AsyncMock()
    with patch("app.routers.correcciones.CorreccionService") as MockSvc, patch(
        "app.routers.correcciones.filtrar_entregas_accesibles",
        AsyncMock(return_value=({1, 2}, set())),
    ):
        MockSvc.return_value.encolar_lote = AsyncMock(return_value=[1, 2])
        res, _ = await _lote(TUTOR, db, [1, 2])
    assert res.omitidas == 0
    assert res.entrega_ids_omitidos == []


def test_lote_schema_omitidos_tiene_defaults_contrato_aditivo():
    r = CorregirLoteAceptadoResponse(mensaje="ok", total_encoladas=1, entrega_ids=[1])
    assert r.omitidas == 0
    assert r.entrega_ids_omitidos == []
