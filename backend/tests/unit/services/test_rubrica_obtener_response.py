"""
Regression tests for RubricaService.obtener_rubrica response building.

Guards against the bug where `obtener_rubrica` built `RubricaDetailResponse`
field-by-field and dropped `modo_consolidacion` / `extensiones_personalizadas`,
so the API always returned the schema default ("solo_codigo") regardless of the
value stored in the database. The bug was invisible to the correction flow
(which reads the field straight from the ORM), but the edit modal always showed
"solo_codigo".

These tests mock the repository, so they need no real database. That is
deliberate: the Rubrica model uses PostgreSQL-only column types (JSONB / ARRAY)
that the SQLite in-memory test harness in conftest.py cannot create, which is
why the DB-backed rubrica service tests cannot run there.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import FuenteRubricaEnum, TipoRubricaEnum
from app.services.rubrica_service import RubricaService


def _fake_rubrica(**overrides) -> SimpleNamespace:
    """Build a fake ORM-like rubrica with every attribute the response needs."""
    materia = SimpleNamespace(id=1, codigo="PROG1", nombre="Programación 1")
    base = dict(
        id=10,
        materia_id=1,
        tipo=TipoRubricaEnum.TP,
        numero=1,
        anio=2026,
        titulo="TP1 - Listas",
        descripcion="Rúbrica de prueba",
        puntaje_maximo=100,
        metadata_json={},
        criterios_json=[],
        penalizaciones_json=[],
        condiciones_desaprobacion_json=[],
        fuente=FuenteRubricaEnum.MANUAL,
        archivo_original=None,
        activa=True,
        moodle_assign_id=None,
        modo_consolidacion="proyecto_completo",
        extensiones_personalizadas=None,
        schema_version=1,
        created_at="2026-06-15T00:00:00",
        updated_at="2026-06-15T00:00:00",
        materia=materia,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service_with_rubrica(rubrica: SimpleNamespace) -> RubricaService:
    """Build a RubricaService whose repo returns the given fake rubrica."""
    service = RubricaService(db=MagicMock())
    service.rubrica_repo = MagicMock()
    service.rubrica_repo.get_by_id_with_relations = AsyncMock(return_value=rubrica)
    service.rubrica_repo.count_entregas = AsyncMock(return_value=0)
    return service


@pytest.mark.asyncio
async def test_obtener_rubrica_devuelve_modo_consolidacion_real():
    """Debe devolver el modo_consolidacion guardado, no el default del schema."""
    rubrica = _fake_rubrica(modo_consolidacion="proyecto_completo")
    service = _service_with_rubrica(rubrica)

    result = await service.obtener_rubrica(10)

    # Si el constructor vuelve a omitir el campo, Pydantic devolvería "solo_codigo".
    assert result.modo_consolidacion == "proyecto_completo"


@pytest.mark.asyncio
async def test_obtener_rubrica_propaga_extensiones_personalizadas():
    """En modo 'personalizado' debe propagar las extensiones guardadas."""
    rubrica = _fake_rubrica(
        modo_consolidacion="personalizado",
        extensiones_personalizadas=[".ipynb", ".sql"],
    )
    service = _service_with_rubrica(rubrica)

    result = await service.obtener_rubrica(10)

    assert result.modo_consolidacion == "personalizado"
    assert result.extensiones_personalizadas == [".ipynb", ".sql"]
