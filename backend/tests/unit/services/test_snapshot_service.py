"""
Tests del SnapshotService (cálculo + persistencia del snapshot — T5).

Moodle y repos mockeados. Cubre la orquestación: filtra students, calcula estado
por alumno (vía avance_mapper), parsea comisión y arma el snapshot.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.models.enums import EstadoAvanceEnum, OrigenSnapshotEnum
from app.services.snapshot_service import SnapshotService

SECCIONES = [
    {"id": 100, "section": 1, "name": "1- Uno", "modules": [
        {"id": 11, "modname": "assign", "name": "Cierre U1", "completion": 2},
    ]},
    {"id": 200, "section": 7, "name": "2- Dos", "modules": [
        {"id": 22, "modname": "quiz", "name": "Quiz U2", "completion": 2},
        {"id": 23, "modname": "assign", "name": "Cierre U2", "completion": 2},
    ]},
]

ENROLLED = [
    {
        "id": 1, "firstname": "Ana", "lastname": "Gómez", "email": "ana@x.com",
        "roles": [{"shortname": "student"}],
        "groups": [{"name": "M26 C1-09"}],
    },
    {
        "id": 2, "firstname": "Beto", "lastname": "Páez", "email": "beto@x.com",
        "roles": [{"shortname": "student"}],
        "groups": [],
    },
    {  # profesor → se ignora
        "id": 3, "firstname": "Prof", "lastname": "X", "email": "p@x.com",
        "roles": [{"shortname": "editingteacher"}],
        "groups": [],
    },
]

COMPLETION = {
    1: [  # Ana: completó hasta U2 → AL_DIA (unidad_actual=2)
        {"cmid": 11, "state": 2, "timecompleted": 100},
        {"cmid": 22, "state": 1, "timecompleted": 300},
        {"cmid": 23, "state": 1, "timecompleted": 400},
    ],
    2: [  # Beto: nada completado → SIN_ACTIVIDAD
        {"cmid": 11, "state": 0, "timecompleted": 0},
    ],
}


def _make_service() -> SnapshotService:
    service = SnapshotService(db=MagicMock())
    service.materia_repo = AsyncMock()
    service.avance_repo = AsyncMock()
    service.moodle = AsyncMock()
    return service


def _materia_configurada():
    return MagicMock(
        id=7,
        moodle_course_id=38,
        unidad_actual=2,
        moodle_section_fin_id=None,
        unidades=[
            MagicMock(numero=1, moodle_section_id=100),
            MagicMock(numero=2, moodle_section_id=200),
        ],
    )


@pytest.mark.asyncio
async def test_generar_materia_inexistente_lanza_404():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.generar(999, token="t", moodle_host="h")

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_generar_materia_sin_configurar_lanza_400():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(
        id=7, moodle_course_id=38, unidad_actual=None, unidades=[]
    )

    with pytest.raises(HTTPException) as exc:
        await service.generar(7, token="t", moodle_host="h")

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_generar_arma_snapshot_con_estados_y_comision():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    service.moodle.get_course_contents.return_value = SECCIONES
    service.moodle.get_enrolled_users_full.return_value = ENROLLED

    async def _completion(token, host, course_id, uid, client=None):
        return COMPLETION[uid]

    service.moodle.get_activities_completion.side_effect = _completion
    service.avance_repo.crear.side_effect = lambda snap: snap  # devuelve el mismo snapshot

    snapshot = await service.generar(7, token="t", moodle_host="h", origen=OrigenSnapshotEnum.MANUAL)

    # Solo los 2 students (el profesor se ignora)
    assert snapshot.total_alumnos == 2
    assert snapshot.unidad_actual == 2
    assert snapshot.origen == OrigenSnapshotEnum.MANUAL

    por_uid = {a.moodle_user_id: a for a in snapshot.alumnos}
    assert por_uid[1].estado == EstadoAvanceEnum.AL_DIA
    assert por_uid[1].unidad_alcanzada == 2
    assert por_uid[1].comision == "M26 C1-09"
    assert por_uid[1].actividad_actual_nombre == "Cierre U2"  # mayor timecompleted en U2
    assert por_uid[1].actividad_actual_desaprobada is False

    assert por_uid[2].estado == EstadoAvanceEnum.SIN_ACTIVIDAD
    assert por_uid[2].unidad_alcanzada is None
    assert por_uid[2].comision is None  # sin grupo de comisión

    # 1 llamada de completion por student (serial)
    assert service.moodle.get_activities_completion.await_count == 2


@pytest.mark.asyncio
async def test_generar_persiste_via_repo():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    service.moodle.get_course_contents.return_value = SECCIONES
    service.moodle.get_enrolled_users_full.return_value = ENROLLED

    async def _completion(token, host, course_id, uid, client=None):
        return COMPLETION[uid]

    service.moodle.get_activities_completion.side_effect = _completion
    service.avance_repo.crear.side_effect = lambda snap: snap

    await service.generar(7, token="t", moodle_host="h")

    service.avance_repo.crear.assert_awaited_once()


@pytest.mark.asyncio
async def test_generar_todas_continua_ante_fallo_de_una_materia():
    service = _make_service()
    service.usuario_repo = AsyncMock()
    service.usuario_repo.get_by_id.return_value = MagicMock(
        id=1, moodle_username="u", moodle_password_encrypted="enc", moodle_host="h"
    )
    service.moodle.get_token.return_value = "tok"
    service.materia_repo.get_configuradas_dashboard.return_value = [
        MagicMock(id=10),
        MagicMock(id=20),
    ]
    # La primera materia genera OK, la segunda revienta → no debe frenar al resto.
    service.generar = AsyncMock(side_effect=[MagicMock(), RuntimeError("boom")])

    result = await service.generar_todas_para_usuario(1, origen=OrigenSnapshotEnum.CRON)

    assert len(result) == 1  # solo la exitosa
    assert service.generar.await_count == 2


@pytest.mark.asyncio
async def test_generar_todas_usuario_sin_credenciales_lanza_valueerror():
    service = _make_service()
    service.usuario_repo = AsyncMock()
    service.usuario_repo.get_by_id.return_value = MagicMock(
        id=1, moodle_username=None, moodle_password_encrypted=None
    )

    with pytest.raises(ValueError):
        await service.generar_todas_para_usuario(1)
