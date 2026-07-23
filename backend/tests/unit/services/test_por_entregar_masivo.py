"""Tests para PorEntregarService.entregar_masivo_stream ('Entregar todos').

Aísla la orquestación del masivo: mockea el repo, MoodleService (token + grades) y
la sesión por tarea. Verifica que sólo se suban las TP, que las YA calificadas en
Moodle se registren sin reenviar, que un 409 cuente como 'ya enviada', que un error
no aborte el lote, y que un fallo de verificación no pise la nota.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException

from app.models.enums import RolEnum
from app.repositories.usuario_repository import CredencialesMoodle
from app.services.moodle_service import MoodleConnectionError
from app.services.por_entregar_service import PorEntregarService


def _correccion(cid, *, tipo="TP", moodle_user_id=101, nota=85, alumno="Selene"):
    materia = MagicMock(moodle_course_id=38)
    comision = MagicMock(materia=materia)
    rubrica = MagicMock(moodle_assign_id=478)
    rubrica.tipo = MagicMock(value=tipo)
    entrega = MagicMock(
        alumno_nombre=alumno, moodle_user_id=moodle_user_id,
        comision=comision, rubrica=rubrica,
    )
    return MagicMock(id=cid, nota=nota, entrega=entrega)


class _FakeSessionCtx:
    async def __aenter__(self):
        return AsyncMock()

    async def __aexit__(self, *a):
        return False


def _tutor():
    return MagicMock(
        id=7, rol=RolEnum.TUTOR, moodle_host="https://m",
        moodle_username="t", moodle_password_encrypted="e",
    )


def _svc(correcciones, *, grades=None, sub_tms=None, token_ok=True, grades_error=False):
    svc = PorEntregarService(AsyncMock())
    svc.correccion_repo = AsyncMock()
    svc.correccion_repo.get_pendientes_subida_moodle = AsyncMock(return_value=correcciones)
    svc.moodle_sync_repo = AsyncMock()
    svc.moodle_sync_repo.contar_por_correccion = AsyncMock(return_value=0)
    svc.moodle_sync_repo.create = AsyncMock(side_effect=lambda s: s)
    svc.usuario_repo = AsyncMock()
    # Fase 3 multi-tenant: la fuente de credenciales es el resolver (repo).
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle("https://m", "t", "e")
    )
    svc.moodle = AsyncMock()
    svc.moodle.get_token = (
        AsyncMock(return_value="tok") if token_ok
        else AsyncMock(side_effect=MoodleConnectionError("Moodle caído"))
    )
    svc.moodle._get_course_assignment_map = AsyncMock(return_value={478: 1000})
    svc.moodle.get_grades_full = (
        AsyncMock(side_effect=MoodleConnectionError("grades fail")) if grades_error
        else AsyncMock(return_value=grades or {})
    )
    # timemodified de las submissions por userid (item #3b): default {} = sin re-entrega.
    svc.moodle.get_submission_timemod_map = AsyncMock(return_value=sub_tms or {})
    return svc


async def _drain(agen):
    return [ev async for ev in agen]


@pytest.mark.asyncio
async def test_solo_tp_se_suben_no_tp_omitidas():
    correcciones = [
        _correccion(1, tipo="TP", moodle_user_id=101),
        _correccion(2, tipo="TP", moodle_user_id=102),
        _correccion(3, tipo="FINAL", moodle_user_id=103, alumno="Ana"),
    ]
    svc = _svc(correcciones, grades={})  # nadie calificado en Moodle

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(return_value=MagicMock())
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["enviadas"] == 2
    assert resumen["omitidas_requieren_comentario"] == 1
    assert resumen["ya_calificadas_en_moodle"] == 0
    llamadas_ids = {c.kwargs["correccion_id"] for c in cls.return_value.subir_correccion.call_args_list}
    assert llamadas_ids == {1, 2}


@pytest.mark.asyncio
async def test_ya_calificada_en_moodle_se_registra_y_no_se_sube():
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    # El alumno 101 YA tiene nota en Moodle (timemodified > 0).
    svc = _svc(correcciones, grades={101: {"timemodified": 99999, "grade": "1.00000"}})

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["ya_calificadas_en_moodle"] == 1
    assert resumen["enviadas"] == 0
    assert eventos[0] == {"tipo": "inicio", "total": 0}  # nada que subir
    cls.return_value.subir_correccion.assert_not_called()
    # Se registró el MoodleSync para que no reaparezca, con la nota de Moodle humanizada.
    svc.moodle_sync_repo.create.assert_awaited_once()
    sync = svc.moodle_sync_repo.create.call_args.args[0]
    assert sync.nota_enviada == "1"
    assert "ya calificada en moodle" in (sync.comentario_enviado or "").lower()


@pytest.mark.asyncio
async def test_reentrega_se_resube_con_forzar():
    # Hay nota en Moodle (timemodified=100) PERO el alumno re-entregó después (500): item #3b.
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    svc = _svc(
        correcciones,
        grades={101: {"timemodified": 100, "grade": "1.00000"}},
        sub_tms={101: 500},
    )

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(return_value=MagicMock())
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["reenviadas_reentrega"] == 1
    assert resumen["ya_calificadas_en_moodle"] == 0
    assert resumen["enviadas"] == 0
    # Se subió forzando (pisa la nota vieja con la nueva de la re-entrega).
    cls.return_value.subir_correccion.assert_awaited_once()
    assert cls.return_value.subir_correccion.call_args.kwargs["forzar"] is True


@pytest.mark.asyncio
async def test_mezcla_una_calificada_y_una_pendiente():
    correcciones = [
        _correccion(1, tipo="TP", moodle_user_id=101),  # ya en Moodle
        _correccion(2, tipo="TP", moodle_user_id=102),  # pendiente
    ]
    svc = _svc(correcciones, grades={101: {"timemodified": 5, "grade": "85.0"}})

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(return_value=MagicMock())
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["ya_calificadas_en_moodle"] == 1
    assert resumen["enviadas"] == 1
    assert eventos[0] == {"tipo": "inicio", "total": 1}
    llamadas_ids = {c.kwargs["correccion_id"] for c in cls.return_value.subir_correccion.call_args_list}
    assert llamadas_ids == {2}  # sólo la pendiente


@pytest.mark.asyncio
async def test_entregada_sin_calificar_no_cuenta_como_ya_en_moodle():
    # grade=-1 (entregó pero sin nota) NO es "ya calificada": debe subirse.
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    svc = _svc(correcciones, grades={101: {"timemodified": 99999, "grade": "-1.00000"}})

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(return_value=MagicMock())
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["ya_calificadas_en_moodle"] == 0
    assert resumen["enviadas"] == 1
    svc.moodle_sync_repo.create.assert_not_called()
    cls.return_value.subir_correccion.assert_awaited_once()


@pytest.mark.asyncio
async def test_409_cuenta_como_ya_enviada():
    correcciones = [_correccion(1, moodle_user_id=101), _correccion(2, moodle_user_id=102)]
    svc = _svc(correcciones, grades={})

    async def _subir(**kwargs):
        if kwargs["correccion_id"] == 2:
            raise HTTPException(status_code=409, detail="ya enviada")
        return MagicMock()

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(side_effect=_subir)
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["enviadas"] == 1
    assert resumen["ya_enviadas"] == 1
    assert resumen["errores"] == []


@pytest.mark.asyncio
async def test_error_no_aborta_el_lote():
    correcciones = [
        _correccion(1, moodle_user_id=101, alumno="A"),
        _correccion(2, moodle_user_id=102, alumno="B"),
        _correccion(3, moodle_user_id=103, alumno="C"),
    ]
    svc = _svc(correcciones, grades={})

    async def _subir(**kwargs):
        if kwargs["correccion_id"] == 2:
            raise HTTPException(status_code=502, detail="Moodle caído")
        return MagicMock()

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(side_effect=_subir)
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["enviadas"] == 2
    assert len(resumen["errores"]) == 1
    assert resumen["errores"][0]["alumno"] == "B"


@pytest.mark.asyncio
async def test_token_falla_emite_error():
    svc = _svc([_correccion(1)], token_ok=False)

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    assert eventos[-1]["tipo"] == "error"
    cls.return_value.subir_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_verificacion_fallida_no_pisa_la_nota():
    correcciones = [_correccion(1, moodle_user_id=101, alumno="A")]
    svc = _svc(correcciones, grades_error=True)  # falla el fetch de grades

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    resumen = eventos[-1]
    assert resumen["enviadas"] == 0
    assert len(resumen["errores"]) == 1
    cls.return_value.subir_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_resuelve_credenciales_de_la_universidad_activa():
    """Fase 3 multi-tenant: el service pide la terna al resolver con
    (usuario.id, ctx.universidad_id) — nunca lee usuario.moodle_*."""
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    svc = _svc(correcciones, grades={})
    ctx = MagicMock(universidad_id=42)

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock(return_value=MagicMock())
        await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=ctx))

    svc.usuario_repo.get_credenciales_moodle.assert_awaited_once_with(7, 42)
    kwargs = svc.moodle.get_token.call_args.kwargs
    assert kwargs["moodle_host"] == "https://m"
    assert kwargs["username"] == "t"


@pytest.mark.asyncio
async def test_sin_membresia_en_universidad_activa_emite_error():
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    svc = _svc(correcciones, grades={})
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(return_value=None)

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    assert eventos[-1]["tipo"] == "error"
    cls.return_value.subir_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_host_null_de_universidad_activa_emite_error_sin_fallback():
    """D1/OP-1: host NULL de la universidad activa -> evento error, SIN fallback."""
    correcciones = [_correccion(1, tipo="TP", moodle_user_id=101)]
    svc = _svc(correcciones, grades={})
    svc.usuario_repo.get_credenciales_moodle = AsyncMock(
        return_value=CredencialesMoodle(None, "t", "e")
    )

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    assert eventos[-1]["tipo"] == "error"
    assert "campus" in eventos[-1]["detail"].lower()
    cls.return_value.subir_correccion.assert_not_called()


@pytest.mark.asyncio
async def test_sin_automaticas_emite_inicio_cero_y_resumen():
    correcciones = [_correccion(1, tipo="FINAL")]
    svc = _svc(correcciones)

    with patch("app.services.por_entregar_service.MoodleGradeService") as cls, patch(
        "app.services.por_entregar_service.async_session_maker", return_value=_FakeSessionCtx()
    ):
        cls.return_value.subir_correccion = AsyncMock()
        eventos = await _drain(svc.entregar_masivo_stream(_tutor(), "http://test", ctx=MagicMock()))

    assert eventos[0] == {"tipo": "inicio", "total": 0}
    assert eventos[-1]["tipo"] == "resumen"
    assert eventos[-1]["omitidas_requieren_comentario"] == 1
    cls.return_value.subir_correccion.assert_not_called()
    svc.moodle.get_token.assert_not_called()  # ni siquiera pide token
