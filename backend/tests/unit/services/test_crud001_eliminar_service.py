"""
CRUD-001 (Fase 3): EntregaService.eliminar_entrega / _masivo / restaurar_entrega.

- Default (ALLOW_HARD_DELETE=False): soft delete (deleted_at), NO toca la Correccion,
  registra Actividad ENTREGA_ELIMINADA.
- ALLOW_HARD_DELETE=True: borrado fisico con cascada (comportamiento previo) + Actividad.
- Doble borrado logico -> 400; id inexistente -> 404.
- restaurar_entrega -> 404 si no existe, 400 si no estaba borrada, Actividad ENTREGA_RESTAURADA.

El repo y ActividadService se mockean: aca importa la ORQUESTACION (que rama se
llama, que se audita), no la persistencia (ya cubierta en el test de repo).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import TipoActividadEnum
from app.services.entrega_service import EntregaService


def _entrega(id=42, alumno="Perez Juan", deleted=False):
    return SimpleNamespace(
        id=id,
        alumno_nombre=alumno,
        deleted_at=object() if deleted else None,
        is_deleted=deleted,
    )


def _service_con_repo(get_by_id=None):
    svc = EntregaService.__new__(EntregaService)  # sin __init__ (no queremos DB real)
    svc.db = MagicMock()
    svc.entrega_repo = MagicMock()
    svc.entrega_repo.get_by_id = AsyncMock(return_value=get_by_id)
    svc.entrega_repo.get_by_ids = AsyncMock()
    svc.entrega_repo.delete = AsyncMock()
    svc.entrega_repo.soft_delete = AsyncMock()
    svc.entrega_repo.restore = AsyncMock()
    svc.entrega_repo.delete_by_ids = AsyncMock(return_value=0)
    svc.entrega_repo.soft_delete_by_ids = AsyncMock(return_value=0)
    return svc


# ===================== eliminar_entrega (individual) =====================


@pytest.mark.asyncio
async def test_eliminar_soft_por_defecto_no_toca_correccion_y_audita():
    svc = _service_con_repo(get_by_id=_entrega())
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ) as MockAct:
        st.ALLOW_HARD_DELETE = False
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.eliminar_entrega(42, actor_id=5)

        svc.entrega_repo.soft_delete.assert_awaited_once()   # rama soft
        svc.entrega_repo.delete.assert_not_called()          # NO fisico
        kwargs = MockAct.return_value.registrar_actividad.await_args.kwargs
    assert kwargs["tipo"] == TipoActividadEnum.ENTREGA_ELIMINADA
    assert kwargs["usuario_id"] == 5
    assert kwargs["entidad_id"] == 42


@pytest.mark.asyncio
async def test_eliminar_hard_cuando_flag_activo_y_audita():
    svc = _service_con_repo(get_by_id=_entrega())
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ) as MockAct:
        st.ALLOW_HARD_DELETE = True
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.eliminar_entrega(42, actor_id=5)

        svc.entrega_repo.delete.assert_awaited_once()        # rama fisica
        svc.entrega_repo.soft_delete.assert_not_called()
        MockAct.return_value.registrar_actividad.assert_awaited_once()


@pytest.mark.asyncio
async def test_eliminar_doble_borrado_logico_da_400():
    svc = _service_con_repo(get_by_id=_entrega(deleted=True))
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ):
        st.ALLOW_HARD_DELETE = False
        with pytest.raises(HTTPException) as exc:
            await svc.eliminar_entrega(42, actor_id=5)
    assert exc.value.status_code == 400
    svc.entrega_repo.soft_delete.assert_not_called()  # no pisa el deleted_at original


@pytest.mark.asyncio
async def test_eliminar_inexistente_da_404():
    svc = _service_con_repo(get_by_id=None)
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ):
        st.ALLOW_HARD_DELETE = False
        with pytest.raises(HTTPException) as exc:
            await svc.eliminar_entrega(999, actor_id=5)
    assert exc.value.status_code == 404


# ===================== eliminar_entregas_masivo =====================


@pytest.mark.asyncio
async def test_masivo_soft_registra_una_sola_actividad_con_ids_en_metadatos():
    svc = _service_con_repo()
    svc.entrega_repo.get_by_ids = AsyncMock(
        return_value=[_entrega(1), _entrega(2), _entrega(3)]
    )
    svc.entrega_repo.soft_delete_by_ids = AsyncMock(return_value=3)
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ) as MockAct:
        st.ALLOW_HARD_DELETE = False
        MockAct.return_value.registrar_actividad = AsyncMock()
        res = await svc.eliminar_entregas_masivo([1, 2, 3], actor_id=7)

        svc.entrega_repo.soft_delete_by_ids.assert_awaited_once_with([1, 2, 3])
        # UNA sola Actividad por lote (no una por entrega).
        assert MockAct.return_value.registrar_actividad.await_count == 1
        kwargs = MockAct.return_value.registrar_actividad.await_args.kwargs
    assert res.procesadas == 3
    assert '"ids"' in kwargs["metadatos"] and "1" in kwargs["metadatos"]
    assert kwargs["usuario_id"] == 7


@pytest.mark.asyncio
async def test_masivo_hard_cuando_flag_activo():
    svc = _service_con_repo()
    svc.entrega_repo.get_by_ids = AsyncMock(return_value=[_entrega(1), _entrega(2)])
    svc.entrega_repo.delete_by_ids = AsyncMock(return_value=2)
    with patch("app.services.entrega_service.settings") as st, patch(
        "app.services.entrega_service.ActividadService"
    ) as MockAct:
        st.ALLOW_HARD_DELETE = True
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.eliminar_entregas_masivo([1, 2], actor_id=7)
        svc.entrega_repo.delete_by_ids.assert_awaited_once_with([1, 2])
        svc.entrega_repo.soft_delete_by_ids.assert_not_called()


@pytest.mark.asyncio
async def test_masivo_id_faltante_da_404():
    svc = _service_con_repo()
    svc.entrega_repo.get_by_ids = AsyncMock(return_value=[_entrega(1)])  # falta el 2
    with patch("app.services.entrega_service.settings"), patch(
        "app.services.entrega_service.ActividadService"
    ):
        with pytest.raises(HTTPException) as exc:
            await svc.eliminar_entregas_masivo([1, 2], actor_id=7)
    assert exc.value.status_code == 404


# ===================== restaurar_entrega =====================


@pytest.mark.asyncio
async def test_restaurar_ok_y_audita():
    svc = _service_con_repo(get_by_id=_entrega(deleted=True))
    with patch("app.services.entrega_service.ActividadService") as MockAct:
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.restaurar_entrega(42, actor_id=5)

        svc.entrega_repo.restore.assert_awaited_once()
        kwargs = MockAct.return_value.registrar_actividad.await_args.kwargs
    assert kwargs["tipo"] == TipoActividadEnum.ENTREGA_RESTAURADA
    assert kwargs["usuario_id"] == 5


@pytest.mark.asyncio
async def test_restaurar_inexistente_da_404():
    svc = _service_con_repo(get_by_id=None)
    with patch("app.services.entrega_service.ActividadService"):
        with pytest.raises(HTTPException) as exc:
            await svc.restaurar_entrega(999, actor_id=5)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_restaurar_entrega_no_borrada_da_400():
    svc = _service_con_repo(get_by_id=_entrega(deleted=False))
    with patch("app.services.entrega_service.ActividadService"):
        with pytest.raises(HTTPException) as exc:
            await svc.restaurar_entrega(42, actor_id=5)
    assert exc.value.status_code == 400
    svc.entrega_repo.restore.assert_not_called()


@pytest.mark.asyncio
async def test_restaurar_lee_con_include_deleted():
    """Sin include_deleted, get_by_id no veria la entrega borrada y siempre daria 404."""
    svc = _service_con_repo(get_by_id=_entrega(deleted=True))
    with patch("app.services.entrega_service.ActividadService") as MockAct:
        MockAct.return_value.registrar_actividad = AsyncMock()
        await svc.restaurar_entrega(42, actor_id=5)
        _, kwargs = svc.entrega_repo.get_by_id.await_args
    assert kwargs.get("include_deleted") is True
