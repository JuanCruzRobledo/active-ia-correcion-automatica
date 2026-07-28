"""
Tests del UnidadService (ABM Unidades + config dashboard de materia — T3).

Repositorios mockeados: se cubre la LÓGICA de validación (materia/unidad not-found,
numero/section duplicados, cuatrimestre inexistente, vínculo rúbrica de otra materia,
desvinculación de rúbricas al borrar).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.unidad import Unidad
from app.repositories.usuario_repository import CredencialesMoodle
from app.schemas.unidad import (
    MateriaDashboardConfig,
    RubricaUnidadAssign,
    UnidadCreate,
)
from app.services.unidad_service import UnidadService


def _make_service() -> UnidadService:
    service = UnidadService(db=MagicMock())
    service.unidad_repo = AsyncMock()
    service.materia_repo = AsyncMock()
    service.cuatrimestre_repo = AsyncMock()
    service.rubrica_repo = AsyncMock()
    service.usuario_repo = AsyncMock()
    # Fase 3 multi-tenant: la fuente de credenciales es el resolver (repo).
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("http://moodle", "u", "enc")
    )
    service.moodle = AsyncMock()
    return service


def _usuario_con_moodle():
    return MagicMock(id=1)


def _materia_mock(**attrs):
    """Materia MagicMock con `universidad_id=None` por defecto (evita disparar el
    guard OQ1 en tests que no lo ejercitan explícitamente)."""
    base = {"universidad_id": None}
    base.update(attrs)
    return MagicMock(**base)


def _unidad(id_: int = 1, materia_id: int = 1, numero: int = 1, section: int = 100) -> Unidad:
    u = Unidad(materia_id=materia_id, numero=numero, moodle_section_id=section, nombre=None)
    u.id = id_
    return u


# ===================== Unidades =====================


@pytest.mark.asyncio
async def test_crear_unidad_materia_inexistente_lanza_404():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.crear_unidad(999, UnidadCreate(numero=1, moodle_section_id=100))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_crear_unidad_numero_duplicado_lanza_409():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=1)
    service.unidad_repo.exists_numero.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.crear_unidad(1, UnidadCreate(numero=2, moodle_section_id=100))

    assert exc.value.status_code == 409
    service.unidad_repo.create.assert_not_called()


@pytest.mark.asyncio
async def test_crear_unidad_section_duplicada_lanza_409():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=1)
    service.unidad_repo.exists_numero.return_value = False
    service.unidad_repo.exists_section.return_value = True

    with pytest.raises(HTTPException) as exc:
        await service.crear_unidad(1, UnidadCreate(numero=2, moodle_section_id=2598))

    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_crear_unidad_happy_path():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=1)
    service.unidad_repo.exists_numero.return_value = False
    service.unidad_repo.exists_section.return_value = False
    service.unidad_repo.create.return_value = _unidad(id_=7, numero=2, section=2598)

    result = await service.crear_unidad(1, UnidadCreate(numero=2, moodle_section_id=2598))

    assert result.numero == 2 and result.moodle_section_id == 2598
    service.unidad_repo.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_eliminar_unidad_borra_via_repo():
    service = _make_service()
    unidad = _unidad()
    service.unidad_repo.get_by_id.return_value = unidad

    await service.eliminar_unidad(1)

    # delete() del repo es quien desvincula las rúbricas y borra
    service.unidad_repo.delete.assert_awaited_once_with(unidad)


# ===================== Config dashboard =====================


@pytest.mark.asyncio
async def test_set_config_materia_inexistente_lanza_404():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.set_config_materia(999, MateriaDashboardConfig(unidad_actual=5))

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_set_config_materia_cuatrimestre_inexistente_lanza_400():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=1)
    service.cuatrimestre_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.set_config_materia(
            1, MateriaDashboardConfig(cuatrimestre_id=42, unidad_actual=5)
        )

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_set_config_materia_happy_path_aplica_valores():
    service = _make_service()
    materia = MagicMock(id=1)
    service.materia_repo.get_by_id.return_value = materia
    service.cuatrimestre_repo.get_by_id.return_value = MagicMock(id=3)

    result = await service.set_config_materia(
        1,
        MateriaDashboardConfig(cuatrimestre_id=3, unidad_actual=5, moodle_section_fin_id=2657),
    )

    assert materia.cuatrimestre_id == 3
    assert materia.unidad_actual == 5
    assert materia.moodle_section_fin_id == 2657
    assert result.unidad_actual == 5
    service.materia_repo.update.assert_awaited_once_with(materia)


# ===================== Vínculo rúbrica → unidad =====================


@pytest.mark.asyncio
async def test_vincular_rubrica_unidad_de_otra_materia_lanza_400():
    service = _make_service()
    service.rubrica_repo.get_by_id.return_value = MagicMock(id=10, materia_id=1)
    service.unidad_repo.get_by_id.return_value = _unidad(id_=5, materia_id=2)  # otra materia

    with pytest.raises(HTTPException) as exc:
        await service.vincular_rubrica_unidad(10, 5)

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_vincular_rubrica_unidad_happy_path():
    service = _make_service()
    rubrica = MagicMock(id=10, materia_id=1)
    service.rubrica_repo.get_by_id.return_value = rubrica
    service.unidad_repo.get_by_id.return_value = _unidad(id_=5, materia_id=1)

    await service.vincular_rubrica_unidad(10, 5)

    assert rubrica.unidad_id == 5
    service.rubrica_repo.update.assert_awaited_once_with(rubrica)


@pytest.mark.asyncio
async def test_desvincular_rubrica_unidad_con_null():
    service = _make_service()
    rubrica = MagicMock(id=10, materia_id=1)
    service.rubrica_repo.get_by_id.return_value = rubrica

    await service.vincular_rubrica_unidad(10, None)

    assert rubrica.unidad_id is None
    service.rubrica_repo.update.assert_awaited_once_with(rubrica)


# ===================== Auto-sugerencia de secciones (Moodle) =====================


@pytest.mark.asyncio
async def test_sugerir_secciones_materia_sin_moodle_lanza_404():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_mock(id=1, moodle_course_id=None)

    with pytest.raises(HTTPException) as exc:
        await service.sugerir_secciones_moodle(1, _usuario_con_moodle(), universidad_id=1)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_sugerir_secciones_sin_credenciales_lanza_424():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_mock(id=1, moodle_course_id=38)
    service.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)

    with pytest.raises(HTTPException) as exc:
        await service.sugerir_secciones_moodle(1, _usuario_con_moodle(), universidad_id=1)

    assert exc.value.status_code == 424


@pytest.mark.asyncio
async def test_sugerir_secciones_materia_de_otra_universidad_lanza_409():
    """OQ1: guard defensivo — la materia debe pertenecer a la universidad activa."""
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_mock(
        id=1, moodle_course_id=38, universidad_id=2
    )

    with pytest.raises(HTTPException) as exc:
        await service.sugerir_secciones_moodle(1, _usuario_con_moodle(), universidad_id=1)

    assert exc.value.status_code == 409
    service.moodle.get_token.assert_not_called()


@pytest.mark.asyncio
async def test_sugerir_secciones_detecta_cabeceras_y_marca_items():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_mock(id=1, moodle_course_id=38)
    service.moodle.get_token.return_value = "tok"
    service.moodle.get_course_contents.return_value = [
        {"id": 2597, "section": 0, "name": "General", "modules": []},
        {"id": 2598, "section": 1, "name": "1- Secuenciales", "modules": []},
        {"id": 2610, "section": 7, "name": "2- Condicionales", "modules": []},
    ]

    result = await service.sugerir_secciones_moodle(1, _usuario_con_moodle(), universidad_id=1)

    assert [c.numero for c in result.cabeceras_sugeridas] == [1, 2]
    assert len(result.secciones) == 3
    cabecera = next(s for s in result.secciones if s.moodle_section_id == 2598)
    assert cabecera.es_cabecera_sugerida and cabecera.numero_sugerido == 1
    general = next(s for s in result.secciones if s.moodle_section_id == 2597)
    assert general.es_cabecera_sugerida is False
    service.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(1, 1)
