"""Tests de inyección de `schema_version` en el payload de rúbrica.

Change: peso-por-subcriterio (D5/D6): `_build_correction_payload` y
`_build_pdf_correction_payload` deben incluir `"schema_version":
rubrica.schema_version` dentro del dict de rúbrica que viaja a los builders
de prompt (Gemini/OpenRouter), para que puedan ramificar v1/v2.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.models.enums import TipoRubricaEnum
from app.services.correccion_service import CorreccionService


def _fake_entrega() -> SimpleNamespace:
    return SimpleNamespace(
        contenido_consolidado="print(1)",
        contenido_preview="print(1)",
        pdf_contenido_b64="ZmFrZS1wZGY=",
        alumno_nombre="Juan Pérez",
        comision=SimpleNamespace(materia=SimpleNamespace(nombre="Programación 1")),
    )


def _fake_rubrica(schema_version: int) -> SimpleNamespace:
    return SimpleNamespace(
        titulo="TP1",
        descripcion="desc",
        tipo=TipoRubricaEnum.TP,
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[{"id": "C1", "peso": 100, "subcriterios": []}],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        schema_version=schema_version,
    )


def _service() -> CorreccionService:
    return CorreccionService(db=MagicMock())


def test_build_correction_payload_inyecta_schema_version_1():
    service = _service()
    payload = service._build_correction_payload(_fake_entrega(), _fake_rubrica(1), "api-key")
    assert payload["rubrica"]["schema_version"] == 1


def test_build_correction_payload_inyecta_schema_version_2():
    service = _service()
    payload = service._build_correction_payload(_fake_entrega(), _fake_rubrica(2), "api-key")
    assert payload["rubrica"]["schema_version"] == 2


def test_build_pdf_correction_payload_inyecta_schema_version_1():
    service = _service()
    payload = service._build_pdf_correction_payload(_fake_entrega(), _fake_rubrica(1), "api-key")
    assert payload["rubrica"]["schema_version"] == 1


def test_build_pdf_correction_payload_inyecta_schema_version_2():
    service = _service()
    payload = service._build_pdf_correction_payload(_fake_entrega(), _fake_rubrica(2), "api-key")
    assert payload["rubrica"]["schema_version"] == 2
