"""Tests de persistencia de `subcriterios_evaluados` en `criterios_json`.

Change: peso-por-subcriterio (D6): al corregir una entrega de rúbrica
schema_version=2, el desglose por subcriterio que devuelve la IA debe quedar
guardado DENTRO de cada criterio en la columna JSONB `criterios_json` de la
corrección (sin migración de tabla — es un dict libre). Correcciones v1/viejas
(sin el campo) deben seguir persistiendo y leyéndose exactamente igual.

Se mockea todo el árbol de dependencias de `corregir_individual`
(repos + cliente Gemini), siguiendo el patrón mock-heavy ya usado en
test_rubrica_schema_version_service.py / test_rubrica_actualizar_moodle_id.py:
el modelo usa columnas JSONB/ARRAY que el harness SQLite no puede crear.
"""

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import EstadoEntregaEnum, TipoRubricaEnum
from app.services.correccion_service import CorreccionService


def _fake_entrega(**overrides) -> SimpleNamespace:
    base = dict(
        id=1,
        universidad_id=1,
        archivo_tipo="txt",
        contenido_consolidado="print(1)",
        contenido_preview="print(1)",
        pdf_contenido_b64=None,
        rubrica_id=5,
        alumno_nombre="Juan Pérez",
        comision=SimpleNamespace(materia=SimpleNamespace(nombre="Programación 1")),
        estado=EstadoEntregaEnum.SUBIDA,
        error_code=None,
        error_mensaje=None,
        error_at=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _fake_rubrica(schema_version: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=5,
        titulo="TP1",
        descripcion="desc",
        tipo=TipoRubricaEnum.TP,
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[{"id": "C1", "peso": 100, "subcriterios": []}],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        schema_version=schema_version,
        condicion_desaprobacion_json=[],
    )


def _gemini_result_v2() -> dict:
    return {
        "success": True,
        "correccion": {
            "nota": 90,
            "criterios": [
                {
                    "id": "C1",
                    "nombre": "Criterio 1",
                    "puntaje_obtenido": 90,
                    "puntaje_maximo": 100,
                    "estado": "OK",
                    "feedback": "Bien",
                    "subcriterios_evaluados": [
                        {
                            "id": "C1.1",
                            "puntaje_obtenido": 50,
                            "puntaje_maximo": 50,
                            "estado": "OK",
                            "feedback": "ok",
                        },
                        {
                            "id": "C1.2",
                            "puntaje_obtenido": 40,
                            "puntaje_maximo": 50,
                            "estado": "OK",
                            "feedback": "casi",
                        },
                    ],
                }
            ],
            "fortalezas": ["ok"],
            "recomendaciones": ["mejorar"],
            "comentario_general": "Bien",
        },
    }


def _gemini_result_v1() -> dict:
    return {
        "success": True,
        "correccion": {
            "nota": 90,
            "criterios": [
                {
                    "id": "C1",
                    "nombre": "Criterio 1",
                    "puntaje_obtenido": 90,
                    "puntaje_maximo": 100,
                    "estado": "OK",
                    "feedback": "Bien",
                }
            ],
            "fortalezas": ["ok"],
            "recomendaciones": ["mejorar"],
            "comentario_general": "Bien",
        },
    }


def _service_con(entrega, rubrica, gemini_result) -> tuple[CorreccionService, dict]:
    """Arma un CorreccionService con los repos mockeados y captura la
    `Correccion` pasada a `correccion_repo.create` (lo que se persistiría)."""
    service = CorreccionService(db=MagicMock())
    service.entrega_repo = MagicMock()
    service.entrega_repo.get_by_id_with_relations = AsyncMock(return_value=entrega)
    service.entrega_repo.update = AsyncMock(return_value=entrega)
    service.entrega_repo.reclamar_para_correccion = AsyncMock(return_value=True)  # IA-003

    service.rubrica_repo = MagicMock()
    service.rubrica_repo.get_active_by_id = AsyncMock(return_value=rubrica)

    service.correccion_repo = MagicMock()
    service.correccion_repo.get_by_entrega_id = AsyncMock(return_value=None)

    captured = {}

    async def _create(correccion):
        captured["correccion"] = correccion
        correccion.id = 100
        # Simula lo que la DB real setea al persistir (server_default / commit).
        correccion.editado_manualmente = correccion.editado_manualmente or False
        correccion.created_at = datetime(2026, 7, 18)
        correccion.updated_at = datetime(2026, 7, 18)
        return correccion

    service.correccion_repo.create = AsyncMock(side_effect=_create)

    # _build_correccion_response recarga con relations: devolvemos un
    # SimpleNamespace "duck-typed" (no la instancia SQLAlchemy real) con
    # `.entrega.rubrica`, para no pelear con los descriptores de relationship
    # de SQLAlchemy (que rechazan asignar un SimpleNamespace como hijo).
    entrega.rubrica = rubrica

    async def _get_by_id_with_relations(correccion_id):
        correccion = captured["correccion"]
        return SimpleNamespace(
            id=correccion.id,
            entrega_id=correccion.entrega_id,
            nota=correccion.nota,
            nota_antes_penalizaciones=correccion.nota_antes_penalizaciones,
            condicion_desaprobacion_aplicada=correccion.condicion_desaprobacion_aplicada,
            penalizaciones_aplicadas=correccion.penalizaciones_aplicadas,
            criterios_json=correccion.criterios_json,
            fortalezas=correccion.fortalezas,
            recomendaciones=correccion.recomendaciones,
            comentario_general=correccion.comentario_general,
            editado_manualmente=correccion.editado_manualmente,
            corregido_por_id=correccion.corregido_por_id,
            created_at=correccion.created_at,
            updated_at=correccion.updated_at,
            entrega=entrega,
        )

    service.correccion_repo.get_by_id_with_relations = AsyncMock(
        side_effect=_get_by_id_with_relations
    )

    service.gemini_client = MagicMock()
    service.gemini_client.corregir_codigo = AsyncMock(return_value=gemini_result)

    service.usuario_repo = MagicMock()

    return service, captured


@pytest.fixture(autouse=True)
def _no_real_decrypt(monkeypatch):
    """No hay una API key real encriptada en el test — pasamos el valor tal cual."""
    monkeypatch.setattr(
        "app.services.correccion_service.decrypt_api_key", lambda v: v
    )


@pytest.mark.asyncio
async def test_corregir_individual_v2_persiste_subcriterios_evaluados_en_criterios_json():
    entrega = _fake_entrega()
    rubrica = _fake_rubrica(schema_version=2)
    service, captured = _service_con(entrega, rubrica, _gemini_result_v2())

    response = await service.corregir_individual(
        entrega_id=1, api_key_encrypted="fake", corregido_por_id=1
    )

    correccion = captured["correccion"]
    criterio_json = correccion.criterios_json["criterios"][0]
    assert "subcriterios_evaluados" in criterio_json
    assert len(criterio_json["subcriterios_evaluados"]) == 2
    assert criterio_json["subcriterios_evaluados"][0]["id"] == "C1.1"
    assert criterio_json["subcriterios_evaluados"][0]["puntaje_obtenido"] == 50.0

    # También expuesto en la respuesta de la API.
    assert response.criterios[0].subcriterios_evaluados is not None
    assert response.criterios[0].subcriterios_evaluados[0].id == "C1.1"


@pytest.mark.asyncio
async def test_corregir_individual_v1_persiste_sin_subcriterios_evaluados():
    """TRIANGULATE (5.3): rúbrica v1 — el campo ni siquiera aparece, igual que hoy."""
    entrega = _fake_entrega()
    rubrica = _fake_rubrica(schema_version=1)
    service, captured = _service_con(entrega, rubrica, _gemini_result_v1())

    response = await service.corregir_individual(
        entrega_id=1, api_key_encrypted="fake", corregido_por_id=1
    )

    correccion = captured["correccion"]
    criterio_json = correccion.criterios_json["criterios"][0]
    assert criterio_json.get("subcriterios_evaluados") is None

    # La nota sigue siendo la suma de puntaje_obtenido de los criterios.
    assert float(response.nota) == 90.0
    assert response.criterios[0].subcriterios_evaluados is None


@pytest.mark.asyncio
async def test_editar_correccion_preserva_subcriterios_evaluados_en_edicion_manual():
    """5.2: una edición manual (CorreccionUpdate) no debe perder el desglose."""
    from app.schemas.correccion import CorreccionUpdate

    entrega = _fake_entrega()
    rubrica = _fake_rubrica(schema_version=2)
    entrega.rubrica = rubrica

    correccion = SimpleNamespace(
        id=100,
        entrega_id=1,
        nota=Decimal("90"),
        nota_antes_penalizaciones=None,
        condicion_desaprobacion_aplicada=None,
        penalizaciones_aplicadas=[],
        criterios_json={"criterios": []},
        fortalezas=[],
        recomendaciones=[],
        comentario_general="Bien",
        editado_manualmente=False,
        corregido_por_id=1,
        created_at=datetime(2026, 7, 18),
        updated_at=datetime(2026, 7, 18),
        entrega=entrega,
    )

    service = CorreccionService(db=MagicMock())
    service.correccion_repo = MagicMock()
    service.correccion_repo.get_by_id = AsyncMock(return_value=correccion)
    service.correccion_repo.update = AsyncMock(side_effect=lambda c: c)
    service.correccion_repo.get_by_id_with_relations = AsyncMock(return_value=correccion)

    update = CorreccionUpdate(
        criterios=[
            {
                "id": "C1",
                "nombre": "Criterio 1",
                "puntaje_obtenido": Decimal("90"),
                "puntaje_maximo": Decimal("100"),
                "estado": "OK",
                "feedback": "Bien",
                "subcriterios_evaluados": [
                    {
                        "id": "C1.1",
                        "puntaje_obtenido": Decimal("50"),
                        "puntaje_maximo": Decimal("50"),
                        "estado": "OK",
                        "feedback": "ok",
                    }
                ],
            }
        ]
    )

    response = await service.editar_correccion(100, update, editado_por_id=2)

    persisted_criterio = correccion.criterios_json["criterios"][0]
    assert persisted_criterio["subcriterios_evaluados"][0]["id"] == "C1.1"
    assert response.criterios[0].subcriterios_evaluados[0].id == "C1.1"
