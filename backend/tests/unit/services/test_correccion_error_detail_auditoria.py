"""ERR-007: el detalle HTTP de un fallo del proveedor de IA NO debe filtrar el
str(e) interno (body crudo del proveedor / detalle de validación) al cliente.

El mensaje que viaja en el `detail` debe ser el del catálogo; el str(e) va SOLO
al log del servidor. Los códigos de estado (502) y el marcado de la entrega en
ERROR se preservan (no se toca el flujo de corrección).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import app.services.correccion_service as correccion_mod
from app.core.error_catalog import ERROR_N8N, mensaje_error
from app.core.exceptions import N8NError
from app.models.enums import EstadoEntregaEnum
from app.services.correccion_service import CorreccionService


def _fake_entrega():
    return SimpleNamespace(
        id=7,
        archivo_tipo="zip",
        contenido_preview="print(1)",
        contenido_consolidado="print(1)",
        rubrica_id=2,
        estado=EstadoEntregaEnum.SUBIDA,
        error_code=None,
        error_mensaje=None,
        error_at=None,
    )


@pytest.mark.asyncio
async def test_n8n_error_no_filtra_str_e_en_detail(monkeypatch):
    secreto = "Error HTTP 500: BODY_CRUDO_DEL_PROVEEDOR_SECRETO"

    service = CorreccionService(db=MagicMock())
    entrega = _fake_entrega()
    service.entrega_repo = AsyncMock()
    service.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=entrega)
    service.entrega_repo.update = AsyncMock()
    service.rubrica_repo = AsyncMock()
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=MagicMock())

    monkeypatch.setattr(correccion_mod, "decrypt_api_key", lambda k: "api-key")
    service._build_correction_payload = MagicMock(return_value={})
    service._call_ia_with_retry = AsyncMock(side_effect=N8NError(secreto))

    with pytest.raises(HTTPException) as exc:
        await service.corregir_individual(
            entrega_id=7, api_key_encrypted="enc", corregido_por_id=5, provider="gemini",
        )

    assert exc.value.status_code == 502
    # El detalle es el mensaje del catálogo, SIN el str(e) interno.
    assert exc.value.detail == mensaje_error(ERROR_N8N, "gemini")
    assert secreto not in str(exc.value.detail)
    # La entrega queda marcada en ERROR (comportamiento preservado).
    assert entrega.estado == EstadoEntregaEnum.ERROR
    assert entrega.error_code == ERROR_N8N
