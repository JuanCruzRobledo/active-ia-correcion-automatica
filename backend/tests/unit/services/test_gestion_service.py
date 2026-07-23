"""Tests de GestionService (T5) — orquestación de la pantalla "Gestión".

Mockea MateriaRepository y MoodleService. Verifica: listado de cursos, opciones de
filtro (regionales/comisiones derivadas de participantes), y la consulta con todos
los filtros (rol, estatus, regional, comisión, inactividad), el orden y el total.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.repositories.usuario_repository import CredencialesMoodle
from app.services.gestion_service import (
    AlumnoGestion,
    FiltrosGestion,
    GestionService,
    ResultadoGestion,
)

NOW = 1_700_000_000


def _lca(dias: int) -> int:
    return NOW - dias * 86_400


def _user(uid, first, last, email, roles, groups, lca, suspendido=False):
    return {
        "id": uid, "firstname": first, "lastname": last, "email": email,
        "roles": [{"shortname": r} for r in roles],
        "groups": [{"name": g} for g in groups],
        "lastcourseaccess": lca, "suspendido": suspendido,
    }


def _usuario():
    return MagicMock(id=7)


def _svc(*, users_status=None, users_full=None, materia=True):
    svc = GestionService(AsyncMock())
    svc.materia_repo = AsyncMock()
    svc.materia_repo.get_by_id = AsyncMock(
        return_value=MagicMock(id=1, nombre="Prog I", codigo="P1", moodle_course_id=38, universidad_id=None)
        if materia else None
    )
    svc.usuario_repo = AsyncMock()
    # Fase 3 multi-tenant: la fuente de credenciales es el resolver (repo).
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "u", "enc")
    )
    svc.moodle = AsyncMock()
    svc.moodle.get_token = AsyncMock(return_value="tok")
    svc.moodle.get_enrolled_users_with_status = AsyncMock(return_value=users_status or [])
    svc.moodle.get_enrolled_users_full = AsyncMock(return_value=users_full or [])
    return svc


# --- listar_cursos ------------------------------------------------------------

@pytest.mark.asyncio
async def test_listar_cursos_mapea_materias_con_moodle():
    svc = _svc()
    svc.materia_repo.get_con_moodle = AsyncMock(return_value=[
        MagicMock(id=1, nombre="Prog I", codigo="P1", moodle_course_id=38),
        MagicMock(id=2, nombre="Prog II", codigo="P2", moodle_course_id=42),
    ])
    cursos = await svc.listar_cursos(_usuario())
    assert [c.materia_id for c in cursos] == [1, 2]
    assert cursos[0].moodle_course_id == 38


# --- opciones_filtros ---------------------------------------------------------

@pytest.mark.asyncio
async def test_opciones_filtros_deriva_regionales_y_comisiones():
    users = [
        _user(1, "A", "A", "a@x", ["student"], ["R-Mendoza", "M26 C1-09", "Grupo_104"], _lca(1)),
        _user(2, "B", "B", "b@x", ["student"], ["R-Rosario", "M26 C1-02"], _lca(1)),
        _user(3, "C", "C", "c@x", ["student"], ["R-Mendoza", "M26 C1-09"], _lca(1)),  # repetidos
    ]
    svc = _svc(users_full=users)
    opciones = await svc.opciones_filtros(_usuario(), materia_id=1, universidad_id=1)

    assert opciones.regionales == ["Mendoza", "Rosario"]          # únicas y ordenadas
    assert opciones.comisiones == ["M26 C1-02", "M26 C1-09"]      # sin Grupo_104
    assert len(opciones.roles) == 3
    assert any(o["value"] == "nunca" for o in opciones.inactividad)


# --- consultar: filtros -------------------------------------------------------

def _poblacion():
    return [
        _user(1, "Ana", "Lopez", "ana@x", ["student"], ["R-Mendoza", "M26 C1-09"], _lca(45)),
        _user(2, "Beto", "Diaz", "beto@x", ["student"], ["R-Rosario", "M26 C1-02"], _lca(10)),
        _user(3, "Cira", "Ortiz", "cira@x", ["student"], ["R-Mendoza", "M26 C1-01"], 0, suspendido=True),
        _user(4, "Profe", "Gomez", "prof@x", ["editingteacher"], ["R-Mendoza", "M26 C1-09"], _lca(100)),
    ]


@pytest.mark.asyncio
async def test_consultar_rol_alumno_y_estatus_activo():
    svc = _svc(users_status=_poblacion())
    filtros = FiltrosGestion(rol="student", estatus="activo")
    res = await svc.consultar(_usuario(), materia_id=1, filtros=filtros, now=NOW, universidad_id=1)

    # Ana y Beto (alumnos activos). Cira suspendida y Profe (teacher) quedan fuera.
    assert res.total == 2
    assert [a.email for a in res.items] == ["ana@x", "beto@x"]  # orden por regional: Mendoza < Rosario


@pytest.mark.asyncio
async def test_consultar_estatus_inactivo_trae_suspendidos():
    svc = _svc(users_status=_poblacion())
    filtros = FiltrosGestion(rol="student", estatus="inactivo")
    res = await svc.consultar(_usuario(), materia_id=1, filtros=filtros, now=NOW, universidad_id=1)
    assert [a.email for a in res.items] == ["cira@x"]


@pytest.mark.asyncio
async def test_consultar_filtro_inactividad_1_mes_banda_cerrada():
    svc = _svc(users_status=_poblacion())
    filtros = FiltrosGestion(rol="student", inactividad_tipo="1_mes")  # 30-59 días
    res = await svc.consultar(_usuario(), materia_id=1, filtros=filtros, now=NOW, universidad_id=1)
    # Ana (45 días) entra; Beto (10) no; Cira (nunca) no.
    assert [a.email for a in res.items] == ["ana@x"]


@pytest.mark.asyncio
async def test_consultar_filtro_regional():
    svc = _svc(users_status=_poblacion())
    filtros = FiltrosGestion(rol="student", regionales=["Rosario"])
    res = await svc.consultar(_usuario(), materia_id=1, filtros=filtros, now=NOW, universidad_id=1)
    assert [a.email for a in res.items] == ["beto@x"]


@pytest.mark.asyncio
async def test_consultar_arma_fila_y_humaniza_inactividad():
    svc = _svc(users_status=_poblacion())
    res = await svc.consultar(_usuario(), materia_id=1, filtros=FiltrosGestion(rol="student"), now=NOW, universidad_id=1)
    por_email = {a.email: a for a in res.items}
    assert por_email["ana@x"].regional == "Mendoza"
    assert por_email["ana@x"].comision == "M26 C1-09"
    assert por_email["ana@x"].tiempo_inactividad == "45 días"
    assert por_email["cira@x"].tiempo_inactividad == "Nunca"


@pytest.mark.asyncio
async def test_consultar_orden_regional_luego_comision():
    pobl = [
        _user(1, "X", "X", "x@x", ["student"], ["R-Rosario", "M26 C1-05"], _lca(5)),
        _user(2, "Y", "Y", "y@x", ["student"], ["R-Mendoza", "M26 C1-08"], _lca(5)),
        _user(3, "Z", "Z", "z@x", ["student"], ["R-Mendoza", "M26 C1-03"], _lca(5)),
    ]
    svc = _svc(users_status=pobl)
    res = await svc.consultar(_usuario(), materia_id=1, filtros=FiltrosGestion(), now=NOW, universidad_id=1)
    # Mendoza(C1-03) < Mendoza(C1-08) < Rosario(C1-05)
    assert [a.email for a in res.items] == ["z@x", "y@x", "x@x"]


# --- credenciales / curso ------------------------------------------------------

@pytest.mark.asyncio
async def test_consultar_sin_credenciales_moodle_es_424():
    svc = _svc(users_status=_poblacion())
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as exc:
        await svc.consultar(_usuario(), materia_id=1, filtros=FiltrosGestion(), now=NOW, universidad_id=1)
    assert exc.value.status_code == 424


@pytest.mark.asyncio
async def test_consultar_resuelve_credenciales_de_la_universidad_activa():
    """Fase 3 multi-tenant: el service pide la terna al resolver con
    (usuario.id, universidad_id) — nunca lee usuario.moodle_*."""
    svc = _svc(users_status=_poblacion())
    await svc.consultar(_usuario(), materia_id=1, filtros=FiltrosGestion(), now=NOW, universidad_id=9)
    svc.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(7, 9)


@pytest.mark.asyncio
async def test_consultar_materia_de_otra_universidad_es_409():
    """OQ1: guard defensivo — la materia debe pertenecer a la universidad activa."""
    svc = _svc(users_status=_poblacion())
    svc.materia_repo.get_by_id = AsyncMock(
        return_value=MagicMock(id=1, moodle_course_id=38, universidad_id=2)
    )
    with pytest.raises(HTTPException) as exc:
        await svc.consultar(_usuario(), materia_id=1, filtros=FiltrosGestion(), now=NOW, universidad_id=1)
    assert exc.value.status_code == 409
    svc.moodle.get_token.assert_not_called()


@pytest.mark.asyncio
async def test_exportar_excel_reusa_consultar_y_devuelve_xlsx():
    svc = _svc()
    svc.consultar = AsyncMock(return_value=ResultadoGestion(
        items=[AlumnoGestion("Ana", "Lopez", "a@x", "Mendoza", "M26 C1-01", 5, "5 días", False)],
        total=1,
    ))
    data, filename = await svc.exportar_excel(_usuario(), materia_id=1, filtros=FiltrosGestion(), now=NOW)
    assert filename.endswith(".xlsx")
    assert len(data) > 100  # se generó un workbook real
    svc.consultar.assert_awaited_once()


@pytest.mark.asyncio
async def test_consultar_curso_inexistente_es_404():
    svc = _svc(users_status=_poblacion(), materia=False)
    with pytest.raises(HTTPException) as exc:
        await svc.consultar(_usuario(), materia_id=999, filtros=FiltrosGestion(), now=NOW)
    assert exc.value.status_code == 404
