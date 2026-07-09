"""
Tests del ExamenService (ABM de exámenes — repos mockeados).

Cubre: derivación de número/etiqueta por tipo, asignación de orden al alta y la
validación del vínculo de rescate (debe ser un PARCIAL de la MISMA materia).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import ModoAprobacionEnum, TipoActividadMoodleEnum, TipoExamenEnum


@pytest.fixture(autouse=True)
def _mock_actividad():
    """La auditoría (ActividadService) no es lo que testeamos acá; se mockea."""
    with patch("app.services.examen_service.ActividadService") as m:
        m.return_value.registrar_actividad = AsyncMock()
        yield
from app.schemas.examen import (
    ExamenMateriaCreate,
    ExamenMateriaUpdate,
)
from app.services.examen_service import ExamenService


def _make_service() -> ExamenService:
    service = ExamenService(db=MagicMock())
    service.examen_repo = AsyncMock()
    service.materia_repo = AsyncMock()
    return service


def _examen(id, tipo, *, cmid=100, modo="ESCALA", nota_minima=None, recupera=None, orden=0,
            materia_id=5):
    e = MagicMock()
    e.id = id
    e.materia_id = materia_id
    e.tipo = TipoExamenEnum(tipo)
    e.moodle_cmid = cmid
    e.modo_aprobacion = ModoAprobacionEnum(modo)
    e.nota_minima = nota_minima
    e.recupera_examen_id = recupera
    e.orden = orden
    e.tipo_actividad = TipoActividadMoodleEnum.ASSIGN
    return e


# ===================== schema validators (pydantic) =====================


def test_schema_recuperatorio_sin_vinculo_falla():
    with pytest.raises(ValueError):
        ExamenMateriaCreate(
            tipo=TipoExamenEnum.RECUPERATORIO,
            moodle_cmid=200,
            modo_aprobacion=ModoAprobacionEnum.ESCALA,
        )


def test_schema_numerico_sin_nota_minima_falla():
    with pytest.raises(ValueError):
        ExamenMateriaCreate(
            tipo=TipoExamenEnum.PARCIAL,
            moodle_cmid=100,
            modo_aprobacion=ModoAprobacionEnum.NUMERICO,
        )


def test_schema_parcial_con_vinculo_falla():
    with pytest.raises(ValueError):
        ExamenMateriaCreate(
            tipo=TipoExamenEnum.PARCIAL,
            moodle_cmid=100,
            modo_aprobacion=ModoAprobacionEnum.ESCALA,
            recupera_examen_id=1,
        )


# ===================== crear =====================


@pytest.mark.asyncio
async def test_crear_parcial_asigna_orden_y_deriva_etiqueta():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=5)
    service.examen_repo.max_orden.return_value = 2
    creado = _examen(10, "PARCIAL", orden=3)
    service.examen_repo.create.return_value = creado
    service.examen_repo.get_by_materia.return_value = [
        _examen(7, "PARCIAL", orden=0), _examen(10, "PARCIAL", orden=3)
    ]

    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.PARCIAL, moodle_cmid=100,
        modo_aprobacion=ModoAprobacionEnum.ESCALA,
    )
    r = await service.crear(5, data)

    # orden = max_orden + 1
    assert service.examen_repo.create.call_args[0][0].orden == 3
    # 2º parcial por orden → "Parcial 2"
    assert r.numero == 2
    assert r.etiqueta == "Parcial 2"


@pytest.mark.asyncio
async def test_crear_recuperatorio_vinculo_a_global_ok():
    # Un GLOBAL también es rescatable: un recuperatorio/extensión/extraordinaria
    # puede apuntar a un GLOBAL, igual que a un PARCIAL.
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=5)
    service.examen_repo.get_by_id.return_value = _examen(3, "GLOBAL", materia_id=5)
    service.examen_repo.max_orden.return_value = 0
    creado = _examen(12, "RECUPERATORIO", cmid=200, recupera=3, orden=1)
    service.examen_repo.create.return_value = creado
    service.examen_repo.get_by_materia.return_value = [
        _examen(3, "GLOBAL", orden=0), creado
    ]

    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.RECUPERATORIO, moodle_cmid=200,
        modo_aprobacion=ModoAprobacionEnum.ESCALA, recupera_examen_id=3,
    )
    r = await service.crear(5, data)
    assert r.recupera_examen_id == 3
    assert r.etiqueta == "Recuperatorio 1"


@pytest.mark.asyncio
async def test_crear_recuperatorio_vinculo_a_tipo_invalido_falla():
    # El padre debe ser PARCIAL o GLOBAL: apuntar a otro recuperatorio falla.
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=5)
    service.examen_repo.get_by_id.return_value = _examen(
        3, "RECUPERATORIO", materia_id=5, recupera=1
    )

    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.EXTENSION, moodle_cmid=200,
        modo_aprobacion=ModoAprobacionEnum.ESCALA, recupera_examen_id=3,
    )
    with pytest.raises(HTTPException) as exc:
        await service.crear(5, data)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_recuperatorio_vinculo_otra_materia_falla():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=5)
    service.examen_repo.get_by_id.return_value = _examen(3, "PARCIAL", materia_id=99)

    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.RECUPERATORIO, moodle_cmid=200,
        modo_aprobacion=ModoAprobacionEnum.ESCALA, recupera_examen_id=3,
    )
    with pytest.raises(HTTPException) as exc:
        await service.crear(5, data)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_crear_recuperatorio_vinculo_a_parcial_valido_ok():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(id=5)
    service.examen_repo.get_by_id.return_value = _examen(3, "PARCIAL", materia_id=5)
    service.examen_repo.max_orden.return_value = 0
    creado = _examen(11, "RECUPERATORIO", cmid=200, recupera=3, orden=1)
    service.examen_repo.create.return_value = creado
    service.examen_repo.get_by_materia.return_value = [
        _examen(3, "PARCIAL", orden=0), creado
    ]

    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.RECUPERATORIO, moodle_cmid=200,
        modo_aprobacion=ModoAprobacionEnum.ESCALA, recupera_examen_id=3,
    )
    r = await service.crear(5, data)
    assert r.recupera_examen_id == 3
    assert r.etiqueta == "Recuperatorio 1"


# ===================== actualizar =====================


@pytest.mark.asyncio
async def test_actualizar_no_puede_recuperarse_a_si_mismo():
    service = _make_service()
    service.examen_repo.get_by_id.return_value = _examen(7, "RECUPERATORIO", recupera=3)

    data = ExamenMateriaUpdate(
        tipo=TipoExamenEnum.RECUPERATORIO, moodle_cmid=200,
        modo_aprobacion=ModoAprobacionEnum.ESCALA, recupera_examen_id=7,
    )
    with pytest.raises(HTTPException) as exc:
        await service.actualizar(7, data)
    assert exc.value.status_code == 400


# =====================================================================
# Bug 1 — Tipo de actividad ASSIGN vs QUIZ (test de EXPLORACIÓN)
# =====================================================================
# CRITICAL: estos tests DEBEN FALLAR sobre el código sin arreglar. La falla
# confirma el Bug 1: hoy `ExamenMateria` y sus schemas NO tienen el campo
# `tipo_actividad`, por lo que no hay forma de representar un examen `quiz`.
# Bug Condition (Bug 1): input.examen.actividad_moodle_real == "quiz"
#                        AND NOT existeCampoTipoActividad(examen).
# NOTE: codifican el comportamiento esperado (Property 1 del design) y validarán
# el fix cuando pasen.


def test_schema_create_acepta_y_persiste_tipo_actividad_quiz():
    """Property 1: alta de un examen quiz (Extraordinaria 2/3 sobre Parcial 2).

    Hoy el campo `tipo_actividad` no existe en `ExamenMateriaCreate`: Pydantic lo
    ignora silenciosamente y acceder a `.tipo_actividad` lanza AttributeError (falla).
    """
    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.EXTRAORDINARIA,
        moodle_cmid=17679,
        modo_aprobacion=ModoAprobacionEnum.ESCALA,
        recupera_examen_id=1,
        tipo_actividad="quiz",
    )
    assert data.tipo_actividad == "quiz"


def test_schema_create_default_tipo_actividad_assign():
    """Property 1: un examen sin tipo declarado queda por defecto en `assign`.

    Hoy falla porque el campo no existe (AttributeError al leer `.tipo_actividad`).
    """
    data = ExamenMateriaCreate(
        tipo=TipoExamenEnum.PARCIAL,
        moodle_cmid=17648,
        modo_aprobacion=ModoAprobacionEnum.ESCALA,
    )
    assert data.tipo_actividad == "assign"


def test_schema_update_acepta_tipo_actividad_quiz():
    """Property 1: la edición también debe permitir marcar `quiz`.

    Hoy falla porque `ExamenMateriaUpdate` no tiene el campo (AttributeError).
    """
    data = ExamenMateriaUpdate(
        tipo=TipoExamenEnum.EXTRAORDINARIA,
        moodle_cmid=20467,
        modo_aprobacion=ModoAprobacionEnum.ESCALA,
        recupera_examen_id=1,
        tipo_actividad="quiz",
    )
    assert data.tipo_actividad == "quiz"


def test_modelo_examen_materia_tiene_columna_tipo_actividad():
    """Property 1: `ExamenMateria` debe persistir `tipo_actividad`.

    Hoy falla porque el modelo no tiene esa columna mapeada.
    """
    from app.models.examen_materia import ExamenMateria

    assert hasattr(ExamenMateria, "tipo_actividad")
