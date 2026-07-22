"""
Tests del manejo de errores del proveedor de IA en la generación de rúbrica (ERR-001).

`RubricaIAService.generar_rubrica_desde_pdf` debe capturar las cuatro subclases de
`GeminiError` (`APIKeyInvalidError`, `QuotaExceededError`, `ModelOverloadedError`,
`InsufficientCreditsError`) y traducirlas a un `HTTPException` con status + `error_code`
del catálogo, replicando el estilo de `correccion_service.py`. Además, ante
`APIKeyInvalidError` debe marcar `usuario.gemini_api_key_valid = False`. No debe haber
regresión en el manejo de `N8NTimeoutError` / `N8NError` (que siguen mapeando a 502).

Estos tests mockean el `GeminiCorrectionClient` y el `UsuarioRepository`, así que no
necesitan una base real: el modelo Usuario/Rubrica usa columnas PostgreSQL-only (JSONB)
que el harness SQLite in-memory no puede crear.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.error_catalog import (
    ERROR_API_KEY_INVALID,
    ERROR_OVERLOADED,
    ERROR_RATE_LIMIT,
    ERROR_SIN_CREDITOS,
    mensaje_error,
)
from app.core.exceptions import (
    APIKeyInvalidError,
    InsufficientCreditsError,
    ModelOverloadedError,
    N8NError,
    N8NTimeoutError,
    QuotaExceededError,
)
from app.services.rubrica_ia_service import RubricaIAService


@pytest.fixture(autouse=True)
def _no_decrypt():
    """Evita el descifrado real de la API key: cualquier string cifrado es válido."""
    with patch(
        "app.services.rubrica_ia_service.decrypt_api_key",
        return_value="fake-plain-key",
    ):
        yield


def _fake_pdf() -> SimpleNamespace:
    """PDF válido (nombre .pdf, contenido chico) con `read()` asíncrono."""
    return SimpleNamespace(
        filename="consigna.pdf",
        read=AsyncMock(return_value=b"%PDF-1.4 fake content"),
    )


def _fake_usuario() -> SimpleNamespace:
    """Usuario ORM-like con la key marcada como válida."""
    return SimpleNamespace(id=1, gemini_api_key_valid=True)


def _service_raising(exc: Exception) -> RubricaIAService:
    """Service cuyo cliente Gemini lanza `exc` al generar la rúbrica."""
    service = RubricaIAService(db=MagicMock())
    service.gemini_client = MagicMock()
    service.gemini_client.generar_rubrica = AsyncMock(side_effect=exc)
    service.usuario_repo = MagicMock()
    service.usuario_repo.update = AsyncMock()
    return service


async def _invoke(service: RubricaIAService, usuario: SimpleNamespace) -> HTTPException:
    """Ejecuta la generación esperando un HTTPException y lo devuelve."""
    with pytest.raises(HTTPException) as exc_info:
        await service.generar_rubrica_desde_pdf(
            pdf_file=_fake_pdf(),
            api_key_encrypted="enc",
            usuario=usuario,
            tipo_rubrica="TP",
        )
    return exc_info.value


@pytest.mark.asyncio
async def test_api_key_invalid_devuelve_402_con_error_code():
    service = _service_raising(APIKeyInvalidError("key inválida"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 402
    assert exc.detail["error_code"] == ERROR_API_KEY_INVALID
    assert exc.detail["message"] == mensaje_error(ERROR_API_KEY_INVALID, "gemini")


@pytest.mark.asyncio
async def test_api_key_invalid_marca_key_invalida():
    service = _service_raising(APIKeyInvalidError("key inválida"))
    usuario = _fake_usuario()

    await _invoke(service, usuario)

    assert usuario.gemini_api_key_valid is False
    service.usuario_repo.update.assert_awaited_once_with(usuario)


@pytest.mark.asyncio
async def test_quota_exceeded_devuelve_429():
    service = _service_raising(QuotaExceededError("rate limit"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 429
    assert exc.detail["error_code"] == ERROR_RATE_LIMIT
    assert exc.detail["message"] == mensaje_error(ERROR_RATE_LIMIT, "gemini")
    # La key NO se marca inválida ante rate-limit.
    assert usuario.gemini_api_key_valid is True


@pytest.mark.asyncio
async def test_model_overloaded_devuelve_503():
    service = _service_raising(ModelOverloadedError("overloaded"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 503
    assert exc.detail["error_code"] == ERROR_OVERLOADED
    assert exc.detail["message"] == mensaje_error(ERROR_OVERLOADED, "gemini")


@pytest.mark.asyncio
async def test_insufficient_credits_devuelve_402_sin_creditos():
    service = _service_raising(InsufficientCreditsError("sin créditos"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 402
    assert exc.detail["error_code"] == ERROR_SIN_CREDITOS
    assert exc.detail["message"] == mensaje_error(ERROR_SIN_CREDITOS, "gemini")
    # Sin créditos NO invalida la key.
    assert usuario.gemini_api_key_valid is True


@pytest.mark.asyncio
async def test_n8n_timeout_sigue_en_502_sin_regresion():
    service = _service_raising(N8NTimeoutError("timeout"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 502
    # Se mantiene el detail string plano actual (no el dict de GeminiError).
    assert isinstance(exc.detail, str)


@pytest.mark.asyncio
async def test_n8n_error_sigue_en_502_sin_regresion():
    service = _service_raising(N8NError("boom"))
    usuario = _fake_usuario()

    exc = await _invoke(service, usuario)

    assert exc.status_code == 502
    assert isinstance(exc.detail, str)
    assert usuario.gemini_api_key_valid is True
