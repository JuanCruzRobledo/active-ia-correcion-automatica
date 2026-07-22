"""Tests de `subcriterios_evaluados` en los schemas de corrección.

Change: peso-por-subcriterio (D6): la IA puede devolver, para rúbricas
schema_version=2, un desglose de puntaje por subcriterio dentro de cada
criterio. El campo es SIEMPRE opcional (`| None = None`) para no romper el
parseo de correcciones v1 (sin desglose).

Coherencia de tipos con el nivel criterio:
- `CriterioGeminiSchema` (parseo de la respuesta cruda de la IA) usa
  `RoundedInt` porque Gemini a veces devuelve floats.
- `CriterioEvaluado` (respuesta de la API / persistencia) usa `Decimal`.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from types import SimpleNamespace

from app.schemas.correccion import (
    CorreccionResponse,
    CorreccionUpdate,
    CriterioEvaluado,
    CriterioGeminiSchema,
    GeminiResponse,
)


def _sub_gemini(**overrides) -> dict:
    base = {
        "id": "C1.1",
        "puntaje_obtenido": 8,
        "puntaje_maximo": 10,
        "estado": "OK",
        "feedback": "Cumple la evidencia",
    }
    base.update(overrides)
    return base


def _criterio_gemini(**overrides) -> dict:
    base = {
        "id": "C1",
        "nombre": "Criterio 1",
        "puntaje_obtenido": 18,
        "puntaje_maximo": 20,
        "estado": "OK",
        "feedback": "Buen trabajo",
    }
    base.update(overrides)
    return base


def _gemini_response_payload(**overrides) -> dict:
    base = {
        "nota": 18,
        "criterios": [_criterio_gemini(subcriterios_evaluados=[_sub_gemini(), _sub_gemini(id="C1.2", puntaje_obtenido=10)])],
        "fortalezas": ["ok"],
        "recomendaciones": ["mejorar"],
        "comentario_general": "Bien",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 3.1 — SubcriterioEvaluado (nivel Gemini, RoundedInt) parsea int y float
# ---------------------------------------------------------------------------


def test_criterio_gemini_subcriterio_con_enteros_parsea_ok():
    c = CriterioGeminiSchema(**_criterio_gemini(subcriterios_evaluados=[_sub_gemini()]))
    assert c.subcriterios_evaluados[0].puntaje_obtenido == 8
    assert c.subcriterios_evaluados[0].puntaje_maximo == 10


def test_criterio_gemini_subcriterio_con_floats_redondea():
    """Gemini a veces devuelve floats — deben redondearse a int (RoundedInt)."""
    c = CriterioGeminiSchema(
        **_criterio_gemini(
            subcriterios_evaluados=[_sub_gemini(puntaje_obtenido=8.4, puntaje_maximo=10.0)]
        )
    )
    assert c.subcriterios_evaluados[0].puntaje_obtenido == 8
    assert isinstance(c.subcriterios_evaluados[0].puntaje_obtenido, int)


def test_criterio_gemini_sin_subcriterios_evaluados_default_none():
    """v1: el campo es opcional, ausente por default (no rompe correcciones v1)."""
    c = CriterioGeminiSchema(**_criterio_gemini())
    assert c.subcriterios_evaluados is None


def test_criterio_gemini_subcriterio_estado_invalido_falla():
    with pytest.raises(ValidationError):
        CriterioGeminiSchema(
            **_criterio_gemini(subcriterios_evaluados=[_sub_gemini(estado="INVALIDO")])
        )


# ---------------------------------------------------------------------------
# CriterioEvaluado (nivel API/persistencia, Decimal)
# ---------------------------------------------------------------------------


def test_criterio_evaluado_con_subcriterios_evaluados_decimal():
    c = CriterioEvaluado(
        id="C1",
        nombre="Criterio 1",
        puntaje_obtenido=Decimal("18"),
        puntaje_maximo=Decimal("20"),
        estado="OK",
        feedback="Bien",
        subcriterios_evaluados=[
            {
                "id": "C1.1",
                "puntaje_obtenido": Decimal("8"),
                "puntaje_maximo": Decimal("10"),
                "estado": "OK",
                "feedback": "ok",
            }
        ],
    )
    assert c.subcriterios_evaluados[0].puntaje_obtenido == Decimal("8")
    assert isinstance(c.subcriterios_evaluados[0].puntaje_obtenido, Decimal)


def test_criterio_evaluado_sin_subcriterios_evaluados_default_none():
    c = CriterioEvaluado(
        id="C1",
        nombre="Criterio 1",
        puntaje_obtenido=Decimal("18"),
        puntaje_maximo=Decimal("20"),
        estado="OK",
        feedback="Bien",
    )
    assert c.subcriterios_evaluados is None


# ---------------------------------------------------------------------------
# 3.4 — GeminiResponse completo: subcriterios_evaluados no afecta validate_nota_sum
# ---------------------------------------------------------------------------


def test_gemini_response_con_subcriterios_evaluados_parsea_sin_error():
    response = GeminiResponse.model_validate(_gemini_response_payload())
    assert response.criterios[0].subcriterios_evaluados is not None
    assert len(response.criterios[0].subcriterios_evaluados) == 2
    # La nota sigue siendo la suma de puntaje_obtenido de CRITERIOS (no cambia por el desglose).
    assert response.nota == 18


def test_gemini_response_nota_coincide_con_suma_de_criterios_con_desglose():
    """La nota sigue anclada a la suma de CRITERIOS (no a la de subcriterios).

    D6: el desglose por subcriterio es informativo — no participa del cálculo
    de la nota. `validate_nota_sum` (pre-existente, sin cambios) sigue
    comparando `nota` contra la suma de `puntaje_obtenido` de los criterios.
    """
    payload = _gemini_response_payload(
        nota=18,
        criterios=[
            _criterio_gemini(
                puntaje_obtenido=18,
                puntaje_maximo=20,
                subcriterios_evaluados=[
                    _sub_gemini(puntaje_obtenido=8),
                    _sub_gemini(id="C1.2", puntaje_obtenido=10),
                ],
            )
        ],
    )
    response = GeminiResponse.model_validate(payload)
    assert response.nota == 18


# ---------------------------------------------------------------------------
# 3.5 — TRIANGULATE: respuesta v1 (sin el campo) sigue parseando idéntico a hoy
# ---------------------------------------------------------------------------


def test_gemini_response_sin_subcriterios_evaluados_v1_parsea_identico():
    payload = _gemini_response_payload(
        criterios=[_criterio_gemini()],  # sin subcriterios_evaluados
    )
    response = GeminiResponse.model_validate(payload)
    assert response.criterios[0].subcriterios_evaluados is None
    assert response.nota == 18


# ---------------------------------------------------------------------------
# 3.3 — Propagación en CorreccionUpdate y CorreccionResponse.model_validate
# ---------------------------------------------------------------------------


def test_correccion_update_preserva_subcriterios_evaluados():
    """Una edición manual no debe perder el desglose por subcriterio."""
    update = CorreccionUpdate(
        criterios=[
            {
                "id": "C1",
                "nombre": "Criterio 1",
                "puntaje_obtenido": Decimal("18"),
                "puntaje_maximo": Decimal("20"),
                "estado": "OK",
                "feedback": "Bien",
                "subcriterios_evaluados": [
                    {
                        "id": "C1.1",
                        "puntaje_obtenido": Decimal("8"),
                        "puntaje_maximo": Decimal("10"),
                        "estado": "OK",
                        "feedback": "ok",
                    }
                ],
            }
        ]
    )
    assert update.criterios[0].subcriterios_evaluados is not None
    assert update.criterios[0].subcriterios_evaluados[0].id == "C1.1"


def test_correccion_response_model_validate_propaga_subcriterios_evaluados():
    """CorreccionResponse.model_validate reconstruye desde criterios_json, y
    debe propagar subcriterios_evaluados cuando está presente en el JSONB."""
    fake_correccion = SimpleNamespace(
        id=1,
        entrega_id=1,
        nota=Decimal("18"),
        nota_antes_penalizaciones=None,
        condicion_desaprobacion_aplicada=None,
        penalizaciones_aplicadas=[],
        criterios_json={
            "criterios": [
                {
                    "id": "C1",
                    "nombre": "Criterio 1",
                    "puntaje_obtenido": 18.0,
                    "puntaje_maximo": 20.0,
                    "estado": "OK",
                    "feedback": "Bien",
                    "subcriterios_evaluados": [
                        {
                            "id": "C1.1",
                            "puntaje_obtenido": 8.0,
                            "puntaje_maximo": 10.0,
                            "estado": "OK",
                            "feedback": "ok",
                        }
                    ],
                }
            ]
        },
        fortalezas=[],
        recomendaciones=[],
        comentario_general="Bien",
        editado_manualmente=False,
        corregido_por_id=1,
        created_at="2026-07-18T00:00:00",
        updated_at="2026-07-18T00:00:00",
    )

    response = CorreccionResponse.model_validate(fake_correccion)

    assert response.criterios[0].subcriterios_evaluados is not None
    assert response.criterios[0].subcriterios_evaluados[0].id == "C1.1"


def test_correccion_response_model_validate_sin_subcriterios_evaluados_v1():
    """Correcciones viejas / v1 sin el campo en criterios_json siguen parseando."""
    fake_correccion = SimpleNamespace(
        id=1,
        entrega_id=1,
        nota=Decimal("18"),
        nota_antes_penalizaciones=None,
        condicion_desaprobacion_aplicada=None,
        penalizaciones_aplicadas=[],
        criterios_json={
            "criterios": [
                {
                    "id": "C1",
                    "nombre": "Criterio 1",
                    "puntaje_obtenido": 18.0,
                    "puntaje_maximo": 20.0,
                    "estado": "OK",
                    "feedback": "Bien",
                }
            ]
        },
        fortalezas=[],
        recomendaciones=[],
        comentario_general="Bien",
        editado_manualmente=False,
        corregido_por_id=1,
        created_at="2026-07-18T00:00:00",
        updated_at="2026-07-18T00:00:00",
    )

    response = CorreccionResponse.model_validate(fake_correccion)

    assert response.criterios[0].subcriterios_evaluados is None
