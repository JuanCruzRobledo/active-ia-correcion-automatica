"""
Tests del SnapshotService (cálculo + persistencia — refactor §R3, carga MASIVA).

Moodle y repos mockeados. Cubre la orquestación NUEVA: 1 login + padrón + contenidos
(WS) + export del calificador + CSV de finalización (descargas masivas), parseo en
memoria y armado del snapshot. NO hay llamadas per-alumno.

Sirve también de verificación de PARIDAD: a partir de los 2 CSV masivos, el avance de
cada alumno debe dar lo mismo que daba el flujo viejo (1 completion + 1 nota por alumno).
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import EstadoAvanceEnum, OrigenSnapshotEnum
from app.services.snapshot_service import SnapshotService


@pytest.fixture(autouse=True)
def _mock_actividad():
    """La auditoría (ActividadService) del snapshot manual se mockea en los unit tests."""
    with patch("app.services.snapshot_service.ActividadService") as m:
        m.return_value.registrar_actividad = AsyncMock()
        yield

# course_contents: nombre de módulo → cmid (el puente para parsear ambos CSV).
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

# Export del calificador (TXT/comma): 6 cols fijas + 1 por item ("<Tipo>:<Nombre> (Real)").
# Ana: ambos TP "Aprobado". Beto: sin nota ("-").
EXPORT_CALIF = (
    'Nombre,Apellido(s),"Número de ID",Institución,Departamento,"Dirección de correo",'
    '"Tarea:Cierre U1 (Real)","Tarea:Cierre U2 (Real)"\n'
    '"Ana","Gómez","","","","ana@x.com","Aprobado","Aprobado"\n'
    '"Beto","Páez","","","","beto@x.com","-","-"\n'
)

# CSV de finalización: col0 nombre, col1 email, luego PARES [estado, fecha].
# Ana: Quiz U2 (cmid 22) Finalizado. Beto: No finalizado.
CSV_FIN = (
    ',"Dirección de correo","Quiz U2",""\n'
    '"Ana Gómez","ana@x.com","Finalizado","2026-01-01"\n'
    '"Beto Páez","beto@x.com","No finalizado",""\n'
)


def _make_service() -> SnapshotService:
    service = SnapshotService(db=MagicMock())
    service.materia_repo = AsyncMock()
    service.avance_repo = AsyncMock()
    service.moodle = AsyncMock()
    # crear_cliente_sesion es SINCRÓNICO y devuelve un cliente (con aclose async).
    service.moodle.crear_cliente_sesion = MagicMock(return_value=AsyncMock())
    service.moodle.get_token.return_value = "tok"
    return service


def _usuario():
    return MagicMock(
        id=1, moodle_username="u", moodle_password_encrypted="enc", moodle_host="h"
    )


def _comp(tipo, cmid, fuente):
    return SimpleNamespace(
        tipo=SimpleNamespace(value=tipo),
        moodle_cmid=cmid,
        fuente=SimpleNamespace(value=fuente),
    )


def _examen(id, tipo, cmid, *, modo="ESCALA", nota_minima=None, recupera=None, orden=0):
    return SimpleNamespace(
        id=id,
        tipo=SimpleNamespace(value=tipo),
        moodle_cmid=cmid,
        modo_aprobacion=SimpleNamespace(value=modo),
        nota_minima=nota_minima,
        recupera_examen_id=recupera,
        orden=orden,
    )


def _materia_configurada(examenes=None):
    return MagicMock(
        id=7,
        moodle_course_id=38,
        unidad_actual=2,
        moodle_section_fin_id=None,
        unidades=[
            MagicMock(numero=1, componentes=[_comp("TP", 11, "CALIFICACION")]),
            MagicMock(
                numero=2,
                componentes=[
                    _comp("TP", 23, "CALIFICACION"),
                    _comp("AUTOEVALUACION", 22, "SEGUIMIENTO"),
                ],
            ),
        ],
        examenes=examenes or [],
    )


def _mock_descargas(service):
    service.moodle.get_course_contents.return_value = SECCIONES
    service.moodle.get_enrolled_users_full.return_value = ENROLLED
    service.moodle.descargar_export_calificador.return_value = EXPORT_CALIF
    service.moodle.descargar_reporte_finalizacion_csv.return_value = CSV_FIN
    service.avance_repo.crear.side_effect = lambda snap: snap


@pytest.mark.asyncio
async def test_generar_materia_inexistente_lanza_404():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = None

    with pytest.raises(HTTPException) as exc:
        await service.generar(999, usuario=_usuario())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_generar_materia_sin_configurar_lanza_400():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = MagicMock(
        id=7, moodle_course_id=38, unidad_actual=None, unidades=[]
    )

    with pytest.raises(HTTPException) as exc:
        await service.generar(7, usuario=_usuario())

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_generar_arma_snapshot_con_estados_y_comision():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    _mock_descargas(service)

    snapshot = await service.generar(7, usuario=_usuario(), origen=OrigenSnapshotEnum.MANUAL)

    # Solo los 2 students (el profesor se ignora)
    assert snapshot.total_alumnos == 2
    assert snapshot.unidad_actual == 2
    assert snapshot.origen == OrigenSnapshotEnum.MANUAL

    por_uid = {a.moodle_user_id: a for a in snapshot.alumnos}
    # Ana: ambos TP aprobados + autoeval U2 hecha → alcanzada 2 → AL_DIA
    assert por_uid[1].estado == EstadoAvanceEnum.AL_DIA
    assert por_uid[1].unidad_alcanzada == 2
    assert por_uid[1].comision == "M26 C1-09"
    assert por_uid[1].actividad_actual_nombre == "Unidad 2"
    assert por_uid[1].actividad_actual_desaprobada is False

    # Beto: sin nota ni completion → SIN_ACTIVIDAD
    assert por_uid[2].estado == EstadoAvanceEnum.SIN_ACTIVIDAD
    assert por_uid[2].unidad_alcanzada is None
    assert por_uid[2].comision is None

    # CERO llamadas per-alumno; 1 descarga de cada CSV.
    service.moodle.descargar_export_calificador.assert_awaited_once()
    service.moodle.descargar_reporte_finalizacion_csv.assert_awaited_once()
    service.moodle.login_sesion.assert_awaited_once()


@pytest.mark.asyncio
async def test_generar_calcula_resultados_examenes():
    # Parcial 1 = "Cierre U1" (cmid 11). Ana lo tiene "Aprobado"; Beto "-" (ausente).
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada(
        examenes=[_examen(1, "PARCIAL", 11)]
    )
    _mock_descargas(service)

    snapshot = await service.generar(7, usuario=_usuario())
    por_uid = {a.moodle_user_id: a for a in snapshot.alumnos}

    ana = por_uid[1].resultados_examenes["examenes"]
    assert ana == [{
        "examen_id": 1, "tipo": "PARCIAL", "numero": 1, "etiqueta": "Parcial 1",
        "resultado": "aprobado", "rescatado": False,
    }]
    # Beto: ausente.
    assert por_uid[2].resultados_examenes["examenes"][0]["resultado"] == "ausente"


@pytest.mark.asyncio
async def test_generar_sin_examenes_deja_resultados_none():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    _mock_descargas(service)

    snapshot = await service.generar(7, usuario=_usuario())
    assert all(a.resultados_examenes is None for a in snapshot.alumnos)


@pytest.mark.asyncio
async def test_generar_persiste_via_repo():
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    _mock_descargas(service)

    await service.generar(7, usuario=_usuario())

    service.avance_repo.crear.assert_awaited_once()


@pytest.mark.asyncio
async def test_generar_reusa_sesion_si_se_pasa():
    """Si se pasa una sesión ya logueada, NO re-loguea ni la cierra (lo hace el caller)."""
    service = _make_service()
    service.materia_repo.get_by_id.return_value = _materia_configurada()
    _mock_descargas(service)
    sesion = AsyncMock()

    await service.generar(7, usuario=_usuario(), sesion=sesion)

    service.moodle.login_sesion.assert_not_awaited()  # no re-login
    sesion.aclose.assert_not_awaited()  # no la cierra generar()


@pytest.mark.asyncio
async def test_generar_todas_continua_ante_fallo_de_una_materia():
    service = _make_service()
    service.usuario_repo = AsyncMock()
    service.usuario_repo.get_by_id.return_value = _usuario()
    service.materia_repo.get_configuradas_dashboard.return_value = [
        MagicMock(id=10),
        MagicMock(id=20),
    ]
    # La primera materia genera OK, la segunda revienta → no debe frenar al resto.
    service.generar = AsyncMock(side_effect=[MagicMock(), RuntimeError("boom")])

    result = await service.generar_todas_para_usuario(1, origen=OrigenSnapshotEnum.CRON)

    assert len(result) == 1  # solo la exitosa
    assert service.generar.await_count == 2
    service.moodle.login_sesion.assert_awaited_once()  # 1 sola sesión para todas


@pytest.mark.asyncio
async def test_generar_todas_usuario_sin_credenciales_lanza_valueerror():
    service = _make_service()
    service.usuario_repo = AsyncMock()
    service.usuario_repo.get_by_id.return_value = MagicMock(
        id=1, moodle_username=None, moodle_password_encrypted=None
    )

    with pytest.raises(ValueError):
        await service.generar_todas_para_usuario(1)
