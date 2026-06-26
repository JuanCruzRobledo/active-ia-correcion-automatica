"""
Tests de SyncService — tokens de versión para el banner "hay novedades" (item #2, Capa B).

Un token por recurso = MAX(updated_at)|COUNT. Captura altas y ediciones (cambia el
max) y borrados (cambia el count). El frontend compara el token contra el que tenía
renderizado: si difiere, muestra "hay datos nuevos". Es un HINT global (no scopeado por
usuario): puede sobre-disparar, pero nunca pierde un cambio.
"""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.sync_service import SyncService, construir_token


# ===================== construir_token (puro) =====================


def test_token_sin_filas_es_none():
    assert construir_token(None, 0) == "none"


def test_token_combina_timestamp_y_count():
    assert construir_token(datetime(2026, 6, 24, 11, 0, 0), 42) == "2026-06-24T11:00:00|42"


def test_token_cambia_si_cambia_el_count():
    # Mismo timestamp, distinto count (un borrado) → token distinto.
    ts = datetime(2026, 6, 24, 11, 0, 0)
    assert construir_token(ts, 42) != construir_token(ts, 41)


def test_token_cambia_si_cambia_el_timestamp():
    assert construir_token(datetime(2026, 6, 24, 11, 0, 0), 42) != construir_token(
        datetime(2026, 6, 24, 12, 0, 0), 42
    )


# ===================== get_versiones (con repos mockeados) =====================


@pytest.mark.asyncio
async def test_get_versiones_arma_tokens_por_recurso():
    service = SyncService(db=MagicMock())
    service.entrega_repo = SimpleNamespace(
        version=AsyncMock(return_value=(datetime(2026, 6, 24, 11, 0, 0), 42))
    )
    service.rubrica_repo = SimpleNamespace(
        version=AsyncMock(return_value=(datetime(2026, 6, 23, 9, 0, 0), 10))
    )

    versiones = await service.get_versiones()

    assert versiones == {
        "entregas": "2026-06-24T11:00:00|42",
        "rubricas": "2026-06-23T09:00:00|10",
    }


@pytest.mark.asyncio
async def test_get_versiones_recurso_vacio_es_none():
    service = SyncService(db=MagicMock())
    service.entrega_repo = SimpleNamespace(version=AsyncMock(return_value=(None, 0)))
    service.rubrica_repo = SimpleNamespace(
        version=AsyncMock(return_value=(datetime(2026, 6, 23, 9, 0, 0), 3))
    )

    versiones = await service.get_versiones()

    assert versiones["entregas"] == "none"
    assert versiones["rubricas"] == "2026-06-23T09:00:00|3"
