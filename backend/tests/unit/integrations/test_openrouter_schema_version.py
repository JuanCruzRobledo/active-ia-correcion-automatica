"""Tests de propagación de `schema_version` al proveedor OpenRouter.

Change: peso-por-subcriterio (D5): OpenRouter reusa los builders compartidos
de Gemini (`_build_criterios_texto`), así que el branch v1/v2 debe llegar
también a su prompt y a su `response_format`. v1 no cambia (json_object,
prompt sin desglose); v2 agrega el desglose por subcriterio al prompt y pide
un `response_format` con el JSON schema anidado (`subcriterios_evaluados`).
"""

import asyncio
import json

import pytest

from app.integrations import openrouter_client
from app.integrations.gemini_correction_client import _SCHEMA_CORRECCION_CODIGO_V2

_CRITERIOS_V2 = [
    {
        "id": "C1",
        "nombre": "Criterio 1",
        "peso": 20,
        "descripcion": "desc",
        "subcriterios": [
            {"id": "C1.1", "descripcion": "sub", "evidencias": ["ev"], "peso": 20},
        ],
    }
]


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code

    def json(self):
        return self._json


class _FakeAsyncClient:
    last_body: dict | None = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        _FakeAsyncClient.last_body = kwargs.get("json")
        content = json.dumps(
            {
                "nota": 18,
                "criterios": [
                    {
                        "id": "C1",
                        "nombre": "Criterio 1",
                        "puntaje_obtenido": 18,
                        "puntaje_maximo": 20,
                        "estado": "OK",
                        "feedback": "bien",
                    }
                ],
                "fortalezas": [],
                "recomendaciones": [],
                "comentario_general": "ok",
            }
        )
        return _FakeResponse(
            {
                "choices": [{"message": {"content": content}}],
                "usage": {},
            }
        )


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    _FakeAsyncClient.last_body = None
    monkeypatch.setattr(openrouter_client.httpx, "AsyncClient", _FakeAsyncClient)


def test_openrouter_v1_usa_response_format_json_object_sin_cambios():
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 1},
        "api_key": "sk-or-fake",
    }
    asyncio.run(openrouter_client.corregir(payload))
    assert _FakeAsyncClient.last_body["response_format"] == {"type": "json_object"}
    prompt = _FakeAsyncClient.last_body["messages"][1]["content"]
    assert "[C1.1]" not in prompt


def test_openrouter_default_sin_schema_version_usa_v1():
    """Rúbrica vieja sin `schema_version` en el payload → v1, no rompe."""
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2},
        "api_key": "sk-or-fake",
    }
    asyncio.run(openrouter_client.corregir(payload))
    assert _FakeAsyncClient.last_body["response_format"] == {"type": "json_object"}


def test_openrouter_v2_incluye_desglose_por_subcriterio_en_el_prompt():
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 2},
        "api_key": "sk-or-fake",
    }
    asyncio.run(openrouter_client.corregir(payload))
    prompt = _FakeAsyncClient.last_body["messages"][1]["content"]
    assert "[C1.1] (20 pts) sub" in prompt


def test_openrouter_v2_usa_json_schema_anidado_en_response_format():
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 2},
        "api_key": "sk-or-fake",
    }
    asyncio.run(openrouter_client.corregir(payload))
    response_format = _FakeAsyncClient.last_body["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == _SCHEMA_CORRECCION_CODIGO_V2
