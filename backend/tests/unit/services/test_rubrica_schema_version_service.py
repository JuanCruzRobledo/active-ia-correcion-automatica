"""Tests de RubricaService para la propagación de `schema_version`.

Change: peso-por-subcriterio (D3): `schema_version` debe persistirse en
`crear_rubrica`, respetarse en `actualizar_rubrica` (solo si viene en el
payload), y exponerse en el detalle (`obtener_rubrica`) y en el listado
(`listar_rubricas`) para que el frontend pueda mostrar el badge
"Rúbrica desactualizada" cuando corresponda.

Se mockea el repositorio (sin DB real), siguiendo el patrón de
test_rubrica_actualizar_moodle_id.py.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import FuenteRubricaEnum, RolEnum, TipoRubricaEnum
from app.schemas.rubrica import RubricaCreate, RubricaUpdate
from app.services.rubrica_service import RubricaService

_ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)

_CRITERIO_V1 = {
    "id": "C1",
    "nombre": "Criterio 1",
    "descripcion": "desc",
    "peso": 100,
    "subcriterios": [
        {"id": "C1.1", "descripcion": "sub", "evidencias": ["ev1"]},
    ],
}


def _fake_rubrica(**overrides) -> SimpleNamespace:
    base = dict(
        id=10,
        materia_id=1,
        tipo=TipoRubricaEnum.TP,
        numero=1,
        anio=2026,
        titulo="TP1",
        descripcion="Rúbrica de prueba",
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[_CRITERIO_V1],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        fuente=FuenteRubricaEnum.MANUAL,
        archivo_original=None,
        activa=True,
        moodle_assign_id=None,
        modo_consolidacion="solo_codigo",
        extensiones_personalizadas=None,
        schema_version=1,
        created_at="2026-06-15T00:00:00",
        updated_at="2026-06-15T00:00:00",
        materia=SimpleNamespace(id=1, codigo="PROG1", nombre="Programación 1"),
        entregas=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service_con(rubrica: SimpleNamespace | None = None) -> RubricaService:
    service = RubricaService(db=MagicMock())
    service.rubrica_repo = MagicMock()
    service.materia_repo = MagicMock()
    service.coordinador_materia_repo = MagicMock()
    service.materia_repo.get_active_by_id = AsyncMock(
        return_value=SimpleNamespace(id=1, codigo="PROG1", nombre="Programación 1")
    )
    service.rubrica_repo.exists = AsyncMock(return_value=False)
    # CRUD-011: el chequeo de conflicto pasó de exists() a get_by_materia_tipo_numero().
    service.rubrica_repo.get_by_materia_tipo_numero = AsyncMock(return_value=None)
    # create/update devuelven la misma instancia (ya mutada) para poder inspeccionarla.
    # create simula la asignación de PK que haría la DB real al persistir.
    def _create_side_effect(r):
        r.id = 10
        return r

    service.rubrica_repo.create = AsyncMock(side_effect=_create_side_effect)
    service.rubrica_repo.update = AsyncMock(side_effect=lambda r: r)
    if rubrica is not None:
        service.rubrica_repo.get_by_id = AsyncMock(return_value=rubrica)
        service.rubrica_repo.get_by_id_with_relations = AsyncMock(return_value=rubrica)
        service.rubrica_repo.count_entregas = AsyncMock(return_value=0)
    return service


@pytest.mark.asyncio
async def test_crear_rubrica_persiste_schema_version_1_por_default():
    service = _service_con()
    from unittest.mock import patch

    with patch("app.services.rubrica_service.ActividadService") as MockActividad:
        MockActividad.return_value.registrar_actividad = AsyncMock()
        data = RubricaCreate(
            materia_id=1,
            tipo=TipoRubricaEnum.TP,
            numero=1,
            anio=2026,
            titulo="TP1",
            descripcion="desc",
            criterios_json=[_CRITERIO_V1],
        )
        result = await service.crear_rubrica(data, _ADMIN, current_user_id=1)

    assert result.schema_version == 1


@pytest.mark.asyncio
async def test_crear_rubrica_persiste_schema_version_2_explicito():
    service = _service_con()
    from unittest.mock import patch

    with patch("app.services.rubrica_service.ActividadService") as MockActividad:
        MockActividad.return_value.registrar_actividad = AsyncMock()
        criterio_v2 = dict(_CRITERIO_V1, subcriterios=[
            {"id": "C1.1", "descripcion": "sub", "evidencias": ["ev1"], "peso": 100},
        ])
        data = RubricaCreate(
            materia_id=1,
            tipo=TipoRubricaEnum.TP,
            numero=1,
            anio=2026,
            titulo="TP1",
            descripcion="desc",
            criterios_json=[criterio_v2],
            schema_version=2,
        )
        result = await service.crear_rubrica(data, _ADMIN, current_user_id=1)

    assert result.schema_version == 2


@pytest.mark.asyncio
async def test_actualizar_rubrica_setea_schema_version_cuando_viene():
    rubrica = _fake_rubrica(schema_version=1)
    service = _service_con(rubrica)

    criterio_v2 = dict(_CRITERIO_V1, subcriterios=[
        {"id": "C1.1", "descripcion": "sub", "evidencias": ["ev1"], "peso": 100},
    ])
    result = await service.actualizar_rubrica(
        10,
        RubricaUpdate(criterios_json=[criterio_v2], schema_version=2),
        _ADMIN,
    )

    assert rubrica.schema_version == 2
    assert result.schema_version == 2


@pytest.mark.asyncio
async def test_actualizar_rubrica_preserva_schema_version_si_no_viene():
    rubrica = _fake_rubrica(schema_version=1)
    service = _service_con(rubrica)

    await service.actualizar_rubrica(10, RubricaUpdate(titulo="Nuevo título"), _ADMIN)

    assert rubrica.schema_version == 1


@pytest.mark.asyncio
async def test_obtener_rubrica_expone_schema_version_en_detalle():
    rubrica = _fake_rubrica(schema_version=2)
    service = _service_con(rubrica)

    detalle = await service.obtener_rubrica(10, _ADMIN)

    assert detalle.schema_version == 2


@pytest.mark.asyncio
async def test_listar_rubricas_expone_schema_version_en_items():
    rubrica = _fake_rubrica(schema_version=2, entregas=[])
    service = _service_con()
    service.rubrica_repo.get_all = AsyncMock(return_value=([rubrica], 1))

    listado = await service.listar_rubricas()

    assert listado.items[0].schema_version == 2
