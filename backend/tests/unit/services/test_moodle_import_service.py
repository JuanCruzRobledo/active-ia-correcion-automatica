"""Tests para MoodleImportService (Fase 2 — orquestación de importación).

Se testea la lógica de _importar_par y _es_reentrega con MoodleService y
EntregaService mockeados (sin DB ni red).

Flujo verificado: primero se consulta si la entrega ya existe (verificar_entrega_existente,
barato) y SÓLO se descarga de Moodle lo que falta.
"""

from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.repositories.usuario_repository import CredencialesMoodle
from app.services.entrega_service import ResultadoImportEntrega
from app.services.moodle_import_service import MoodleImportService, ResumenImportacion, _Par
from app.services.moodle_service import MoodleAuthError, MoodleFile, MoodleSubmission


def _par():
    rubrica = MagicMock(
        id=2, titulo="TP3", moodle_assign_id=11237, materia_id=3,
        modo_consolidacion="web_completo", extensiones_personalizadas=None,
    )
    comision = MagicMock(id=5, moodle_group_id=4165, materia_id=3)
    materia = MagicMock(id=3, moodle_course_id=38)
    return _Par(rubrica=rubrica, comision=comision, materia=materia)


@pytest.fixture
def service():
    svc = MoodleImportService(AsyncMock())
    svc.moodle = AsyncMock()
    svc.moodle._get_course_assignment_map = AsyncMock(return_value={11237: 478})
    svc.moodle.get_group_members_map = AsyncMock(return_value={101: "Carlos Brittos", 102: "Ana Gomez"})
    svc.moodle.download_submission_file = AsyncMock(return_value=b"PK\x03\x04bytes")
    svc.entrega_service = AsyncMock()
    # Por defecto: no existe ninguna → todo se importa
    svc.entrega_service.verificar_entrega_existente = AsyncMock(return_value=None)
    return svc


def _sub(userid, timemodified=100, files=None):
    return MoodleSubmission(
        userid=userid, status="submitted", gradingstatus="notgraded",
        timemodified=timemodified, attemptnumber=0,
        files=files if files is not None else [MoodleFile("tp.zip", "https://m/tp.zip")],
    )


@pytest.mark.asyncio
async def test_importar_par_cuenta_creadas_y_sin_archivos(service):
    service.moodle.get_submissions_with_files = AsyncMock(return_value=[
        _sub(101),                 # con archivo → creada
        _sub(102, files=[]),       # sin archivos
    ])
    service.entrega_service.crear_o_actualizar_desde_bytes = AsyncMock(
        return_value=ResultadoImportEntrega(status="creada", entrega_id=1)
    )

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert resumen.cargadas == 1
    assert resumen.sin_archivos == 1
    assert resumen.detalle_por_rubrica[0]["cargadas"] == 1
    args = service.entrega_service.crear_o_actualizar_desde_bytes.call_args.kwargs
    assert args["alumno_nombre"] == "Carlos Brittos"
    assert args["moodle_user_id"] == 101
    # Usa el modo de consolidación de la rúbrica, NO el hardcode 'solo_codigo'
    assert args["modo_consolidacion"] == "web_completo"


@pytest.mark.asyncio
async def test_importar_par_ya_existente_NO_descarga(service):
    """La mejora de eficiencia: si ya existe, no se descarga ni se crea."""
    service.moodle.get_submissions_with_files = AsyncMock(return_value=[_sub(101)])
    service.entrega_service.verificar_entrega_existente = AsyncMock(
        return_value=ResultadoImportEntrega(status="duplicada", entrega_id=7)
    )
    service.entrega_service.crear_o_actualizar_desde_bytes = AsyncMock()

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert resumen.duplicadas == 1
    # No se descargó ni se intentó crear (verificación previa lo evitó)
    service.moodle.download_submission_file.assert_not_called()
    service.entrega_service.crear_o_actualizar_desde_bytes.assert_not_called()


@pytest.mark.asyncio
async def test_importar_par_reentrega_NO_descarga(service):
    # Existe con corrección y el alumno entregó DESPUÉS → reentrega, sin descargar
    service.moodle.get_submissions_with_files = AsyncMock(return_value=[
        _sub(101, timemodified=1735689600),  # 2025-01-01
    ])
    service.entrega_service.verificar_entrega_existente = AsyncMock(
        return_value=ResultadoImportEntrega(
            status="ya_corregida", entrega_id=9, correccion_actualizada_en=datetime(2024, 1, 1)
        )
    )
    service.entrega_service.crear_o_actualizar_desde_bytes = AsyncMock()

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert resumen.reentregas == 1
    assert resumen.omitidas_ya_corregidas == 0
    service.moodle.download_submission_file.assert_not_called()


@pytest.mark.asyncio
async def test_importar_par_ya_corregida_sin_reentrega(service):
    service.moodle.get_submissions_with_files = AsyncMock(return_value=[
        _sub(101, timemodified=1700000000),  # 2023
    ])
    service.entrega_service.verificar_entrega_existente = AsyncMock(
        return_value=ResultadoImportEntrega(
            status="ya_corregida", entrega_id=9, correccion_actualizada_en=datetime(2030, 1, 1)
        )
    )

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert resumen.omitidas_ya_corregidas == 1
    assert resumen.reentregas == 0


@pytest.mark.asyncio
async def test_importar_par_error_no_aborta_lote(service):
    """Una entrega con error de consolidación se reporta pero NO frena las demás."""
    service.moodle.get_submissions_with_files = AsyncMock(return_value=[
        _sub(101),  # ok
        _sub(102),  # falla en consolidación
    ])

    async def crear(**kwargs):
        if kwargs["moodle_user_id"] == 102:
            return ResultadoImportEntrega(status="error", detalle="No se encontraron archivos válidos en el ZIP")
        return ResultadoImportEntrega(status="creada", entrega_id=1)

    service.entrega_service.crear_o_actualizar_desde_bytes = AsyncMock(side_effect=crear)

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert resumen.cargadas == 1
    assert len(resumen.errores) == 1
    assert "archivos válidos" in resumen.errores[0]["motivo"]


@pytest.mark.asyncio
async def test_importar_par_cmid_no_encontrado_reporta_error(service):
    service.moodle._get_course_assignment_map = AsyncMock(return_value={})
    service.moodle.get_submissions_with_files = AsyncMock()

    resumen = ResumenImportacion()
    await service._importar_par(
        token="t", moodle_host="https://m", par=_par(), subido_por_id=9, resumen=resumen
    )

    assert len(resumen.errores) == 1
    assert "no encontrado" in resumen.errores[0]["motivo"]
    service.moodle.get_submissions_with_files.assert_not_called()


def test_es_reentrega():
    sub_2025 = _sub(101, timemodified=1735689600)
    assert MoodleImportService._es_reentrega(sub_2025, datetime(2024, 1, 1)) is True
    assert MoodleImportService._es_reentrega(sub_2025, datetime(2030, 1, 1)) is False
    assert MoodleImportService._es_reentrega(sub_2025, None) is False


@pytest.mark.asyncio
async def test_obtener_bytes_multiples_archivos_arma_zip(service):
    import io, zipfile

    sub = _sub(101, files=[
        MoodleFile("a.py", "https://m/a.py"),
        MoodleFile("b.py", "https://m/b.py"),
    ])
    service.moodle.download_submission_file = AsyncMock(side_effect=[b"print('a')", b"print('b')"])

    contenido, nombre = await service._obtener_bytes("t", sub, "Carlos Brittos")

    assert nombre.endswith(".zip")
    with zipfile.ZipFile(io.BytesIO(contenido)) as zf:
        assert set(zf.namelist()) == {"a.py", "b.py"}


@pytest.mark.asyncio
async def test_importar_stream_emite_inicio_progreso_resumen():
    svc = MoodleImportService(AsyncMock())
    svc.usuario_repo = AsyncMock()
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "u", "e")
    )
    svc.moodle = AsyncMock()
    svc.moodle.get_token = AsyncMock(return_value="tok")
    svc.moodle._get_course_assignment_map = AsyncMock(return_value={11237: 478})
    svc.moodle.get_group_members_map = AsyncMock(return_value={101: "Carlos Brittos", 102: "Ana Gomez"})
    svc.moodle.get_submissions_with_files = AsyncMock(return_value=[_sub(101), _sub(102)])
    svc.moodle.download_submission_file = AsyncMock(return_value=b"PK\x03\x04")
    svc._resolver_pares = AsyncMock(return_value=[_par()])

    es_inst = MagicMock()
    es_inst.verificar_entrega_existente = AsyncMock(return_value=None)
    es_inst.crear_o_actualizar_desde_bytes = AsyncMock(
        return_value=ResultadoImportEntrega(status="creada", entrega_id=1)
    )

    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=AsyncMock())
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("app.services.moodle_import_service.async_session_maker", return_value=cm), \
         patch("app.services.moodle_import_service.EntregaService", return_value=es_inst):
        eventos = [ev async for ev in svc.importar_stream(7, "tutor", universidad_id=1)]

    assert any(e["tipo"] == "preparando" for e in eventos)
    inicio = next(e for e in eventos if e["tipo"] == "inicio")
    assert inicio["total"] == 2
    progresos = [e for e in eventos if e["tipo"] == "progreso"]
    assert len(progresos) == 2
    assert progresos[-1]["procesadas"] == 2
    assert eventos[-1]["tipo"] == "resumen"
    assert eventos[-1]["cargadas"] == 2


@pytest.mark.asyncio
async def test_importar_stream_sin_trabajo_emite_total_0():
    svc = MoodleImportService(AsyncMock())
    svc.usuario_repo = AsyncMock()
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "u", "e")
    )
    svc.moodle = AsyncMock()
    svc.moodle.get_token = AsyncMock(return_value="tok")
    svc._resolver_pares = AsyncMock(return_value=[])  # sin pares → sin trabajo

    eventos = [ev async for ev in svc.importar_stream(7, "tutor", universidad_id=1)]
    inicio = next(e for e in eventos if e["tipo"] == "inicio")
    assert inicio["total"] == 0
    assert eventos[-1]["tipo"] == "resumen"


@pytest.mark.asyncio
async def test_importar_stream_sin_credenciales_emite_evento_error():
    """Fase 3 multi-tenant: sin membresía/credenciales en la universidad activa ->
    el HTTPException 424 del resolver se traduce a MoodleAuthError (consistente
    con el try/except del router, que envuelve el generador en un evento SSE)."""
    svc = MoodleImportService(AsyncMock())
    svc.usuario_repo = AsyncMock()
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)

    with pytest.raises(MoodleAuthError):
        async for _ in svc.importar_stream(7, "tutor", universidad_id=1):
            pass


@pytest.mark.asyncio
async def test_importar_distingue_credenciales_por_universidad(service):
    """El mismo tutor, 2 universidades -> credenciales DISTINTAS resueltas por universidad_id."""
    service.usuario_repo = AsyncMock()
    creds_por_uni = {
        1: CredencialesMoodle("https://a.edu", "user_a", "pass_a"),
        2: CredencialesMoodle("https://b.edu", "user_b", "pass_b"),
    }
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        side_effect=lambda uid, univ_id: creds_por_uni[univ_id]
    )
    service.moodle.get_token = AsyncMock(return_value="tok")
    service._resolver_pares = AsyncMock(return_value=[])

    await service.importar(user_id=7, scope="tutor", universidad_id=1)
    assert service.moodle.get_token.call_args.kwargs["moodle_host"] == "https://a.edu"

    await service.importar(user_id=7, scope="tutor", universidad_id=2)
    assert service.moodle.get_token.call_args.kwargs["moodle_host"] == "https://b.edu"


@pytest.mark.asyncio
async def test_importar_host_null_es_424_sin_fallback(service):
    service.usuario_repo = AsyncMock()
    service.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle(None, "tutor", "enc")
    )

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await service.importar(user_id=7, scope="tutor", universidad_id=1)
    assert exc.value.status_code == 424
    assert "campus" in exc.value.detail.lower()
