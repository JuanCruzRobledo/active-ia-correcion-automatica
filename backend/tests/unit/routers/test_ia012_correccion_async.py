"""
IA-012: la corrección individual ya no bloquea el request HTTP hasta ~3 min.

Ahora el endpoint hace los checks baratos síncronos (acceso, API key), agenda la
corrección en un BackgroundTask y responde 202. El frontend pollea el estado de
la entrega (PENDIENTE → CORREGIDA/ERROR), igual que con el lote. La corrección
real corre en `procesar_individual_background`, que crea su propia sesión y
swallowea los errores al log (el estado de la entrega ya los refleja).
"""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import RolEnum
from app.routers.correcciones import corregir_entrega, recorregir_entrega
from app.services.correccion_service import procesar_individual_background

USER = SimpleNamespace(
    id=5, rol=RolEnum.TUTOR, correction_provider="gemini",
    gemini_api_key_encrypted="k", openrouter_api_key_encrypted=None,
)
USER_SIN_KEY = SimpleNamespace(
    id=6, rol=RolEnum.TUTOR, correction_provider="gemini",
    gemini_api_key_encrypted=None, openrouter_api_key_encrypted=None,
)


class _Bg:
    """BackgroundTasks fake que captura add_task."""

    def __init__(self):
        self.llamadas = []

    def add_task(self, func, **kwargs):
        self.llamadas.append((func, kwargs))


class _FakeSession:
    async def __aenter__(self):
        return MagicMock()

    async def __aexit__(self, *a):
        return False


# ----------------------------------------------- endpoint 202 (no bloquea)

@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [corregir_entrega, recorregir_entrega])
async def test_endpoint_devuelve_202_y_agenda_background(endpoint):
    bg = _Bg()
    with patch("app.routers.correcciones.verificar_acceso_entrega", AsyncMock()), patch(
        "app.routers.correcciones.CorreccionService"
    ) as MockSvc:
        res = await endpoint(42, bg, current_user=USER, db=AsyncMock())
    assert res.entrega_id == 42
    assert res.estado == "PENDIENTE"
    # se agendó exactamente un background task
    assert len(bg.llamadas) == 1
    # NO se llamó al LLM sincrónicamente dentro del request
    MockSvc.return_value.corregir_individual.assert_not_called()
    MockSvc.return_value.recorregir.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [corregir_entrega, recorregir_entrega])
async def test_sin_acceso_403_no_agenda_nada(endpoint):
    bg = _Bg()
    with patch(
        "app.routers.correcciones.verificar_acceso_entrega",
        AsyncMock(side_effect=HTTPException(status_code=403, detail="no")),
    ):
        with pytest.raises(HTTPException) as exc:
            await endpoint(42, bg, current_user=USER, db=AsyncMock())
    assert exc.value.status_code == 403
    assert bg.llamadas == []


@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", [corregir_entrega, recorregir_entrega])
async def test_sin_api_key_400_no_agenda_nada(endpoint):
    bg = _Bg()
    with patch("app.routers.correcciones.verificar_acceso_entrega", AsyncMock()):
        with pytest.raises(HTTPException) as exc:
            await endpoint(42, bg, current_user=USER_SIN_KEY, db=AsyncMock())
    assert exc.value.status_code == 400
    assert bg.llamadas == []


# ----------------------------------------- background: corrige y swallowea

@pytest.mark.asyncio
async def test_background_llama_corregir_individual():
    fake = MagicMock()
    fake.corregir_individual = AsyncMock(return_value="CORR")
    with patch(
        "app.services.correccion_service.async_session_maker", lambda: _FakeSession()
    ), patch("app.services.correccion_service.CorreccionService", return_value=fake):
        await procesar_individual_background(42, "enc", 5, "gemini")
    fake.corregir_individual.assert_awaited_once()
    assert fake.corregir_individual.await_args.kwargs["entrega_id"] == 42


@pytest.mark.asyncio
async def test_background_swallowea_httpexception():
    fake = MagicMock()
    fake.corregir_individual = AsyncMock(
        side_effect=HTTPException(status_code=502, detail="boom")
    )
    with patch(
        "app.services.correccion_service.async_session_maker", lambda: _FakeSession()
    ), patch("app.services.correccion_service.CorreccionService", return_value=fake):
        # No debe propagar: el estado de la entrega ya quedó en ERROR.
        await procesar_individual_background(42, "enc", 5, "gemini")
