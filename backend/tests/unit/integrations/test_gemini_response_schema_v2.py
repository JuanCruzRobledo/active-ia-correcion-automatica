"""Tests de los response schemas v2 (`_SCHEMA_CORRECCION_CODIGO_V2` /
`_SCHEMA_CORRECCION_PDF_V2`) y de la selección por `schema_version` en
`corregir_codigo` / `corregir_pdf`.

Change: peso-por-subcriterio (D5/D6): para rubricas `schema_version=2`, el
`responseSchema` que se le pide a Gemini debe incluir, dentro de cada
criterio, un array `subcriterios_evaluados` con
`id, puntaje_obtenido, puntaje_maximo, estado, feedback`. v1 sigue usando
exactamente el schema actual (`_SCHEMA_CORRECCION_CODIGO` / `..._PDF`).
"""

import asyncio
import base64
import json

import pytest

from app.integrations.gemini_correction_client import (
    GeminiCorrectionClient,
    _SCHEMA_CORRECCION_CODIGO,
    _SCHEMA_CORRECCION_CODIGO_V2,
    _SCHEMA_CORRECCION_PDF,
    _SCHEMA_CORRECCION_PDF_V2,
)


def _subcriterio_item_schema(schema: dict) -> dict:
    criterios_items = schema["properties"]["criterios"]["items"]
    return criterios_items["properties"]["subcriterios_evaluados"]["items"]


# ---------------------------------------------------------------------------
# 4.4 — Estructura de los schemas V2
# ---------------------------------------------------------------------------


def test_schema_codigo_v2_tiene_subcriterios_evaluados_anidado():
    props = _SCHEMA_CORRECCION_CODIGO_V2["properties"]["criterios"]["items"]["properties"]
    assert "subcriterios_evaluados" in props
    sub_item = _subcriterio_item_schema(_SCHEMA_CORRECCION_CODIGO_V2)
    for campo in ("id", "puntaje_obtenido", "puntaje_maximo", "estado", "feedback"):
        assert campo in sub_item["properties"], f"falta {campo} en subcriterios_evaluados"


def test_schema_pdf_v2_tiene_subcriterios_evaluados_anidado():
    props = _SCHEMA_CORRECCION_PDF_V2["properties"]["criterios"]["items"]["properties"]
    assert "subcriterios_evaluados" in props
    sub_item = _subcriterio_item_schema(_SCHEMA_CORRECCION_PDF_V2)
    for campo in ("id", "puntaje_obtenido", "puntaje_maximo", "estado", "feedback"):
        assert campo in sub_item["properties"], f"falta {campo} en subcriterios_evaluados"


def test_schema_v1_no_tiene_subcriterios_evaluados():
    """El schema v1 (existente) queda intacto: sin el nivel de subcriterios."""
    props_codigo = _SCHEMA_CORRECCION_CODIGO["properties"]["criterios"]["items"]["properties"]
    props_pdf = _SCHEMA_CORRECCION_PDF["properties"]["criterios"]["items"]["properties"]
    assert "subcriterios_evaluados" not in props_codigo
    assert "subcriterios_evaluados" not in props_pdf


# ---------------------------------------------------------------------------
# 4.4 — Selección del schema por versión en corregir_codigo / corregir_pdf
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, json_data, status_code=200):
        self._json = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)

    def json(self):
        return self._json


class _FakeAsyncClient:
    """Captura el body de cada POST y devuelve una respuesta Gemini canned."""

    last_body: dict | None = None
    upload_uri = "files/fake-uri"

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        if "upload" in url:
            return _FakeResponse({"file": {"uri": self.upload_uri}})

        _FakeAsyncClient.last_body = kwargs.get("json")
        candidate_text = json.dumps(
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
                "candidates": [{"content": {"parts": [{"text": candidate_text}]}}],
                "usageMetadata": {},
            }
        )


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


@pytest.fixture(autouse=True)
def _reset_fake_client(monkeypatch):
    _FakeAsyncClient.last_body = None
    monkeypatch.setattr(
        "app.integrations.gemini_correction_client.httpx.AsyncClient", _FakeAsyncClient
    )


def test_corregir_codigo_v1_usa_schema_v1():
    client = GeminiCorrectionClient()
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 1},
        "api_key": "fake-key",
    }
    asyncio.run(client.corregir_codigo(payload))
    assert _FakeAsyncClient.last_body["generationConfig"]["responseSchema"] == _SCHEMA_CORRECCION_CODIGO


def test_corregir_codigo_v2_usa_schema_v2():
    client = GeminiCorrectionClient()
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 2},
        "api_key": "fake-key",
    }
    asyncio.run(client.corregir_codigo(payload))
    assert _FakeAsyncClient.last_body["generationConfig"]["responseSchema"] == _SCHEMA_CORRECCION_CODIGO_V2


def test_corregir_codigo_default_sin_schema_version_usa_v1():
    """Payload sin `schema_version` en la rúbrica (rúbricas viejas) → v1, no rompe."""
    client = GeminiCorrectionClient()
    payload = {
        "codigo": "print(1)",
        "rubrica": {"criterios": _CRITERIOS_V2},
        "api_key": "fake-key",
    }
    asyncio.run(client.corregir_codigo(payload))
    assert _FakeAsyncClient.last_body["generationConfig"]["responseSchema"] == _SCHEMA_CORRECCION_CODIGO


def test_corregir_pdf_v1_usa_schema_v1():
    client = GeminiCorrectionClient()
    pdf_b64 = base64.b64encode(b"%PDF-1.4 fake").decode()
    payload = {
        "pdf_base64": pdf_b64,
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 1},
        "api_key": "fake-key",
    }
    asyncio.run(client.corregir_pdf(payload))
    assert _FakeAsyncClient.last_body["generationConfig"]["responseSchema"] == _SCHEMA_CORRECCION_PDF


def test_corregir_pdf_v2_usa_schema_v2():
    client = GeminiCorrectionClient()
    pdf_b64 = base64.b64encode(b"%PDF-1.4 fake").decode()
    payload = {
        "pdf_base64": pdf_b64,
        "rubrica": {"criterios": _CRITERIOS_V2, "schema_version": 2},
        "api_key": "fake-key",
    }
    asyncio.run(client.corregir_pdf(payload))
    assert _FakeAsyncClient.last_body["generationConfig"]["responseSchema"] == _SCHEMA_CORRECCION_PDF_V2
