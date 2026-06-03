"""
Tests del DashboardLecturaService (lecturas del dashboard — T7).

Repos mockeados. Cubre: árbol de selectores, título dinámico (materia vs "Todos"),
agregación de conteos del último snapshot y mapeo del detalle.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.avance import AvanceAlumno
from app.models.enums import EstadoAvanceEnum
from app.services.dashboard_lectura_service import DashboardLecturaService


def _make_service() -> DashboardLecturaService:
    service = DashboardLecturaService(db=MagicMock())
    service.cohorte_repo = AsyncMock()
    service.cuatrimestre_repo = AsyncMock()
    service.materia_repo = AsyncMock()
    service.avance_repo = AsyncMock()
    return service


@pytest.mark.asyncio
async def test_obtener_arbol_arma_cohorte_cuatrimestre_materias():
    service = _make_service()
    cohorte = MagicMock(id=10, codigo="M25", nombre=None)
    cohorte.cuatrimestres = [MagicMock(id=1, numero=1, nombre=None)]
    service.cohorte_repo.get_all.return_value = [cohorte]
    service.materia_repo.get_by_cuatrimestre.return_value = [
        MagicMock(id=5, codigo="P1", nombre="Programación 1")
    ]

    arbol = await service.obtener_arbol()

    assert len(arbol) == 1
    assert arbol[0].codigo == "M25"
    assert arbol[0].cuatrimestres[0].numero == 1
    assert arbol[0].cuatrimestres[0].materias[0].nombre == "Programación 1"


@pytest.mark.asyncio
async def test_avance_materia_puntual_titulo_y_conteos():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = MagicMock(id=1, cohorte_id=10, numero=1)
    service.cohorte_repo.get_by_id.return_value = MagicMock(codigo="M25")
    service.materia_repo.get_by_id.return_value = MagicMock(id=5, nombre="Programación 1")
    service.avance_repo.get_ultimo_snapshot.return_value = MagicMock(
        id=99, generado_en=datetime(2026, 6, 3, 3, 0)
    )
    service.avance_repo.contar_por_estado.return_value = {
        EstadoAvanceEnum.AL_DIA: 10,
        EstadoAvanceEnum.RIESGO_ALTO: 3,
    }

    r = await service.avance(1, materia_id=5)

    assert r.titulo == "M25 · Programación 1"  # materia puntual: no menciona cuatrimestre
    assert r.conteos.al_dia == 10
    assert r.conteos.riesgo_alto == 3
    assert r.conteos.riesgo_medio == 0
    assert r.total == 13


@pytest.mark.asyncio
async def test_avance_todos_titulo_cohorte_cuatrimestre():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = MagicMock(id=1, cohorte_id=10, numero=1)
    service.cohorte_repo.get_by_id.return_value = MagicMock(codigo="M25")
    service.materia_repo.get_by_cuatrimestre.return_value = [
        MagicMock(id=5), MagicMock(id=6)
    ]
    # una materia con snapshot, otra sin
    service.avance_repo.get_ultimo_snapshot.side_effect = [
        MagicMock(id=99, generado_en=datetime(2026, 6, 3)),
        None,
    ]
    service.avance_repo.contar_por_estado.return_value = {EstadoAvanceEnum.SIN_ACTIVIDAD: 5}

    r = await service.avance(1, materia_id=None)

    assert r.titulo == "Cohorte M25 · Cuatrimestre 1"
    assert r.conteos.sin_actividad == 5
    assert r.total == 5


@pytest.mark.asyncio
async def test_avance_sin_snapshots_devuelve_ceros():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = MagicMock(id=1, cohorte_id=10, numero=1)
    service.cohorte_repo.get_by_id.return_value = MagicMock(codigo="M25")
    service.materia_repo.get_by_cuatrimestre.return_value = [MagicMock(id=5)]
    service.avance_repo.get_ultimo_snapshot.return_value = None
    service.avance_repo.contar_por_estado.return_value = {}

    r = await service.avance(1)

    assert r.total == 0
    assert r.generado_en is None


@pytest.mark.asyncio
async def test_avance_cuatrimestre_inexistente_lanza_404():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.avance(999)

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_detalle_mapea_alumnos():
    service = _make_service()
    service.cuatrimestre_repo.get_by_id.return_value = MagicMock(id=1, cohorte_id=10, numero=1)
    service.materia_repo.get_by_id.return_value = MagicMock(id=5, nombre="P1")
    service.avance_repo.get_ultimo_snapshot.return_value = MagicMock(id=99)
    alumno = AvanceAlumno(
        moodle_user_id=1, nombre="Ana", apellido="Gómez", email="ana@x.com",
        comision="M26 C1-09", unidad_alcanzada=2, actividad_actual_nombre="Cierre U2",
        actividad_actual_unidad=2, actividad_actual_desaprobada=False,
        estado=EstadoAvanceEnum.AL_DIA,
    )
    service.avance_repo.get_alumnos_por_estado.return_value = [alumno]

    detalle = await service.detalle(1, EstadoAvanceEnum.AL_DIA, materia_id=5)

    assert len(detalle) == 1
    assert detalle[0].nombre == "Ana"
    assert detalle[0].comision == "M26 C1-09"
    assert detalle[0].actividad_actual_nombre == "Cierre U2"
