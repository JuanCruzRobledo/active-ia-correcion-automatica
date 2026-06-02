"""Tests de GestionService.exportar_pendientes_excel.

Diseño eficiente: 1 query de comisiones+tutores → mapa {moodle_group_id: tutor};
1 query de participantes (get_enrolled_users_full) → nombre/apellido/email + comisión
(del grupo) + tutor (por id de grupo); luego 1 consulta de submissions por rúbrica
(cacheada). NO consulta miembros por comisión ni el tutor por comisión.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.services.gestion_service import GestionService
from app.services.moodle_service import MoodleConnectionError


def _usuario(con_creds=True):
    return MagicMock(
        id=7, moodle_host="https://m",
        moodle_username="u" if con_creds else None,
        moodle_password_encrypted="enc" if con_creds else None,
    )


def _comision_db(group_id, *tutores):
    cts = [MagicMock(tutor=MagicMock(nombre=n)) for n in tutores]
    return MagicMock(moodle_group_id=group_id, tutores=cts)


def _enrolled(uid, first, last, email, comision_name, comision_group_id, rol="student"):
    return {
        "id": uid, "firstname": first, "lastname": last, "email": email,
        "roles": [{"shortname": rol}],
        "groups": [
            {"id": comision_group_id, "name": comision_name},
            {"id": 9001, "name": "R-Mendoza"},
        ],
    }


def _svc(*, rubricas, comisiones_db, enrolled, instance_map, subs_por_instancia):
    svc = GestionService(AsyncMock())
    svc.materia_repo = AsyncMock()
    svc.materia_repo.get_by_id = AsyncMock(
        return_value=MagicMock(id=1, nombre="Prog I", moodle_course_id=38)
    )
    svc.rubrica_repo = AsyncMock()
    svc.rubrica_repo.get_by_materia = AsyncMock(return_value=rubricas)
    svc.comision_repo = AsyncMock()
    svc.comision_repo.get_by_materia_con_tutores = AsyncMock(return_value=comisiones_db)
    svc.moodle = AsyncMock()
    svc.moodle.get_token = AsyncMock(return_value="tok")
    svc.moodle.get_enrolled_users_full = AsyncMock(return_value=enrolled)
    svc.moodle._get_course_assignment_map = AsyncMock(return_value=instance_map)

    async def _subs(token, host, instance_id, member_ids, solo_pendientes=True):
        val = subs_por_instancia.get(instance_id, [])
        if isinstance(val, Exception):
            raise val
        return val

    svc.moodle.get_submissions_with_files = AsyncMock(side_effect=_subs)
    return svc


@pytest.mark.asyncio
async def test_arma_pendiente_con_comision_y_tutor():
    rubricas = [MagicMock(id=1, titulo="TP 1", moodle_assign_id=11237, activa=True)]
    # comisión grupo 4165 → tutor "Matias Torres"
    comisiones_db = [_comision_db(4165, "Matias Torres")]
    enrolled = [_enrolled(101, "Ana", "Lopez", "ana@x", "M26 C1-02", 4165)]
    svc = _svc(
        rubricas=rubricas, comisiones_db=comisiones_db, enrolled=enrolled,
        instance_map={11237: 478},
        subs_por_instancia={478: [MagicMock(userid=101, timemodified=1717000000)]},
    )
    captura = {}
    svc.excel.exportar_pendientes = MagicMock(
        side_effect=lambda pend, nombre, agrupar_por="trabajo": (captura.update(p=pend) or (b"x", "f.xlsx"))
    )

    await svc.exportar_pendientes_excel(_usuario(), materia_id=1, agrupar_por="comision")

    e = captura["p"][0]
    assert (e.trabajo, e.comision, e.tutor, e.email) == ("TP 1", "M26 C1-02", "Matias Torres", "ana@x")
    # 1 sola query de comisiones+tutores y de participantes
    svc.comision_repo.get_by_materia_con_tutores.assert_awaited_once()
    svc.moodle.get_enrolled_users_full.assert_awaited_once()
    assert not svc.moodle._get_group_member_ids.await_count


@pytest.mark.asyncio
async def test_varios_tutores_por_comision_se_juntan():
    rubricas = [MagicMock(id=1, titulo="TP 1", moodle_assign_id=11237, activa=True)]
    comisiones_db = [_comision_db(4165, "Ana Mutti", "Oscar Londero")]
    enrolled = [_enrolled(101, "X", "Y", "x@x", "M26 C1-02", 4165)]
    svc = _svc(
        rubricas=rubricas, comisiones_db=comisiones_db, enrolled=enrolled,
        instance_map={11237: 478},
        subs_por_instancia={478: [MagicMock(userid=101, timemodified=1)]},
    )
    svc.excel.exportar_pendientes = MagicMock(return_value=(b"x", "f.xlsx"))

    await svc.exportar_pendientes_excel(_usuario(), materia_id=1)

    e = svc.excel.exportar_pendientes.call_args.args[0][0]
    assert e.tutor == "Ana Mutti, Oscar Londero"


@pytest.mark.asyncio
async def test_comision_sin_tutor_en_db_queda_vacio():
    rubricas = [MagicMock(id=1, titulo="TP 1", moodle_assign_id=11237, activa=True)]
    comisiones_db = []  # no hay comisión registrada para el grupo del alumno
    enrolled = [_enrolled(101, "Ana", "Lopez", "a@x", "M26 C1-02", 4165)]
    svc = _svc(
        rubricas=rubricas, comisiones_db=comisiones_db, enrolled=enrolled,
        instance_map={11237: 478},
        subs_por_instancia={478: [MagicMock(userid=101, timemodified=1)]},
    )
    svc.excel.exportar_pendientes = MagicMock(return_value=(b"x", "f.xlsx"))

    await svc.exportar_pendientes_excel(_usuario(), materia_id=1)

    e = svc.excel.exportar_pendientes.call_args.args[0][0]
    assert e.comision == "M26 C1-02"  # la comisión sale igual del nombre del grupo
    assert e.tutor == ""              # sin tutor mapeado


@pytest.mark.asyncio
async def test_agrupar_por_se_propaga():
    rubricas = [MagicMock(id=1, titulo="TP 1", moodle_assign_id=11237, activa=True)]
    svc = _svc(
        rubricas=rubricas, comisiones_db=[_comision_db(4165, "T")],
        enrolled=[_enrolled(101, "A", "B", "a@x", "M26 C1-01", 4165)],
        instance_map={11237: 478},
        subs_por_instancia={478: [MagicMock(userid=101, timemodified=1)]},
    )
    svc.excel.exportar_pendientes = MagicMock(return_value=(b"x", "f.xlsx"))

    await svc.exportar_pendientes_excel(_usuario(), materia_id=1, agrupar_por="comision")
    assert svc.excel.exportar_pendientes.call_args.kwargs["agrupar_por"] == "comision"


@pytest.mark.asyncio
async def test_rubrica_que_falla_se_saltea():
    rubricas = [
        MagicMock(id=1, titulo="TP OK", moodle_assign_id=11237, activa=True),
        MagicMock(id=2, titulo="TP FALLA", moodle_assign_id=99999, activa=True),
    ]
    svc = _svc(
        rubricas=rubricas, comisiones_db=[_comision_db(4165, "T")],
        enrolled=[_enrolled(101, "A", "B", "a@x", "M26 C1-01", 4165)],
        instance_map={11237: 478, 99999: 999},
        subs_por_instancia={
            478: [MagicMock(userid=101, timemodified=1)],
            999: MoodleConnectionError("timeout"),
        },
    )
    svc.excel.exportar_pendientes = MagicMock(return_value=(b"x", "f.xlsx"))

    with patch("app.services.gestion_service.asyncio.sleep", AsyncMock()):
        await svc.exportar_pendientes_excel(_usuario(), materia_id=1)

    pend = svc.excel.exportar_pendientes.call_args.args[0]
    assert {e.trabajo for e in pend} == {"TP OK"}


@pytest.mark.asyncio
async def test_sin_credenciales_moodle_es_424():
    svc = _svc(rubricas=[], comisiones_db=[], enrolled=[], instance_map={}, subs_por_instancia={})
    with pytest.raises(HTTPException) as exc:
        await svc.exportar_pendientes_excel(_usuario(con_creds=False), materia_id=1)
    assert exc.value.status_code == 424
