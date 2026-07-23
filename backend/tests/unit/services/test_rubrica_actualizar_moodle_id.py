"""
Tests de RubricaService.actualizar_rubrica para el manejo de `moodle_assign_id`.

Item #6 del plan de fixes: el tutor/coordinador debe poder DEJAR VACÍO (borrar) el
moodle_assign_id de una rúbrica para que deje de aparecer en pendientes. El bug:
`actualizar_rubrica` hacía `if data.moodle_assign_id is not None: ...`, así que un
`null` explícito (borrar) se ignoraba — había que distinguir "no vino el campo" de
"vino en null". La distinción correcta es `model_fields_set` de Pydantic.

Se mockea el repositorio (sin DB real): el modelo Rubrica usa tipos PostgreSQL
(JSONB/ARRAY) que el harness SQLite de conftest.py no puede crear.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import ValidationError

from app.models.enums import FuenteRubricaEnum, RolEnum, TipoRubricaEnum
from app.schemas.rubrica import RubricaUpdate
from app.services.rubrica_service import RubricaService


def _fake_rubrica(**overrides) -> SimpleNamespace:
    """Rúbrica ORM-like con todos los atributos que necesita RubricaResponse."""
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
        moodle_assign_id=123,
        modo_consolidacion="solo_codigo",
        extensiones_personalizadas=None,
        created_at="2026-06-15T00:00:00",
        updated_at="2026-06-15T00:00:00",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _service_con(rubrica: SimpleNamespace) -> RubricaService:
    service = RubricaService(db=MagicMock())
    service.rubrica_repo = MagicMock()
    service.rubrica_repo.get_by_id = AsyncMock(return_value=rubrica)
    # update devuelve la misma instancia (ya mutada) para poder inspeccionarla.
    service.rubrica_repo.update = AsyncMock(side_effect=lambda r: r)
    return service


_ADMIN = SimpleNamespace(id=1, rol=RolEnum.ADMIN)


# ===================== service: borrar / setear / preservar =====================


@pytest.mark.asyncio
async def test_actualizar_borra_moodle_id_cuando_es_null_explicito():
    """data.moodle_assign_id=None EXPLÍCITO → la rúbrica queda en None (se borra)."""
    rubrica = _fake_rubrica(moodle_assign_id=123)
    service = _service_con(rubrica)

    result = await service.actualizar_rubrica(
        10, RubricaUpdate(moodle_assign_id=None), _ADMIN, rol=RolEnum.ADMIN
    )

    assert rubrica.moodle_assign_id is None
    assert result.moodle_assign_id is None


@pytest.mark.asyncio
async def test_actualizar_no_toca_moodle_id_si_no_viene_en_el_payload():
    """Si moodle_assign_id no está en el payload, se preserva el valor existente."""
    rubrica = _fake_rubrica(moodle_assign_id=123)
    service = _service_con(rubrica)

    await service.actualizar_rubrica(10, RubricaUpdate(titulo="Nuevo título"), _ADMIN, rol=RolEnum.ADMIN)

    assert rubrica.moodle_assign_id == 123


@pytest.mark.asyncio
async def test_actualizar_setea_moodle_id_nuevo():
    """Un número válido nuevo se persiste."""
    rubrica = _fake_rubrica(moodle_assign_id=None)
    service = _service_con(rubrica)

    await service.actualizar_rubrica(10, RubricaUpdate(moodle_assign_id=55), _ADMIN, rol=RolEnum.ADMIN)

    assert rubrica.moodle_assign_id == 55


# ===================== schema: validación gt=0 =====================


@pytest.mark.parametrize("valor", [0, -1, -999])
def test_schema_rechaza_moodle_id_no_positivo(valor):
    """0 y negativos no son cmid válidos → ValidationError (422 en la API)."""
    with pytest.raises(ValidationError):
        RubricaUpdate(moodle_assign_id=valor)


@pytest.mark.parametrize("valor", [None, 1, 55, 999999])
def test_schema_acepta_none_o_positivo(valor):
    """None (borrar) y enteros positivos son válidos."""
    data = RubricaUpdate(moodle_assign_id=valor)
    assert data.moodle_assign_id == valor
