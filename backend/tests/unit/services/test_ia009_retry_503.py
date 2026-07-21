"""
IA-009: 503 (ModelOverloadedError) es un error RECUPERABLE (el modelo está
sobrecargado momentáneamente) pero no se reintentaba en el retry interno — se caía
al primer intento. Ahora se reintenta con backoff, como el timeout.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import ModelOverloadedError
from app.services.correccion_service import CorreccionService


def _svc():
    svc = CorreccionService.__new__(CorreccionService)
    svc.gemini_client = SimpleNamespace()
    return svc


@pytest.mark.asyncio
async def test_retry_reintenta_ante_503_y_termina_ok():
    svc = _svc()
    # 1ª llamada: 503; 2ª: OK.
    svc.gemini_client.corregir_codigo = AsyncMock(
        side_effect=[ModelOverloadedError("sobrecargado"), {"success": True}]
    )
    with patch("app.services.correccion_service.asyncio.sleep", AsyncMock()):
        res = await svc._call_ia_with_retry({"x": 1}, provider="gemini", max_retries=1)
    assert res == {"success": True}
    assert svc.gemini_client.corregir_codigo.await_count == 2  # reintentó


@pytest.mark.asyncio
async def test_retry_503_agota_reintentos_y_propaga():
    svc = _svc()
    svc.gemini_client.corregir_codigo = AsyncMock(
        side_effect=ModelOverloadedError("sobrecargado")
    )
    with patch("app.services.correccion_service.asyncio.sleep", AsyncMock()):
        with pytest.raises(ModelOverloadedError):
            await svc._call_ia_with_retry({"x": 1}, provider="gemini", max_retries=1)
    assert svc.gemini_client.corregir_codigo.await_count == 2  # intento + 1 retry


@pytest.mark.asyncio
async def test_retry_pdf_tambien_reintenta_503():
    svc = _svc()
    svc.gemini_client.corregir_pdf = AsyncMock(
        side_effect=[ModelOverloadedError("x"), {"success": True}]
    )
    with patch("app.services.correccion_service.asyncio.sleep", AsyncMock()):
        res = await svc._call_ia_pdf_with_retry({"x": 1}, max_retries=1)
    assert res == {"success": True}
    assert svc.gemini_client.corregir_pdf.await_count == 2
