"""
Tests del EmailService (T3 — wrapper Resend con reintentos + throttle).

El POST a Resend (_post_resend) y el sleep se mockean: NO se manda ningún email
real ni se espera tiempo. enviar_uno MUTA el EnvioEmailLog (estado/resend_id/...).
"""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum
from app.models.notificacion import EnvioEmailLog
from app.services.email_service import EmailService


def _settings(api_key="re_test", rate=1000.0):
    return SimpleNamespace(
        RESEND_API_KEY=api_key,
        EMAIL_REMITENTE="onboarding@resend.dev",
        EMAIL_RATE_POR_SEGUNDO=rate,
    )


def _service(api_key="re_test"):
    return EmailService(db=MagicMock(), settings=_settings(api_key=api_key))


def _log(estado=EstadoEnvioEnum.PENDIENTE):
    return EnvioEmailLog(
        tanda_id="t1",
        tipo=TipoNotificacionEnum.ALUMNO,
        destinatario_email="alumno@x.com",
        asunto="Tus actividades faltantes",
        estado=estado,
        intentos=0,
    )


def _resp(status, body=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.text = text
    return r


@pytest.mark.asyncio
async def test_enviar_uno_exito_marca_enviado_con_resend_id():
    service = _service()
    service._post_resend = AsyncMock(return_value=(200, _resp(200, {"id": "abc123"})))

    log = _log()
    out = await service.enviar_uno(
        log, html="<b>hola</b>", client=MagicMock(), sleep=AsyncMock()
    )

    assert out.estado == EstadoEnvioEnum.ENVIADO
    assert out.resend_id == "abc123"
    assert out.intentos == 1
    assert out.enviado_en is not None
    assert out.error is None


@pytest.mark.asyncio
async def test_enviar_uno_reintenta_en_429_y_luego_ok():
    service = _service()
    service._post_resend = AsyncMock(
        side_effect=[(429, _resp(429, {"message": "rate"})), (200, _resp(200, {"id": "ok"}))]
    )
    sleep = AsyncMock()

    log = _log()
    out = await service.enviar_uno(
        log, html="x", client=MagicMock(), sleep=sleep, max_intentos=3
    )

    assert out.estado == EstadoEnvioEnum.ENVIADO
    assert out.resend_id == "ok"
    assert out.intentos == 2
    sleep.assert_awaited_once()  # esperó 1 backoff entre el 429 y el reintento


@pytest.mark.asyncio
async def test_enviar_uno_4xx_no_reintenta():
    service = _service()
    service._post_resend = AsyncMock(return_value=(422, _resp(422, {"message": "bad to"})))
    sleep = AsyncMock()

    log = _log()
    out = await service.enviar_uno(log, html="x", client=MagicMock(), sleep=sleep)

    assert out.estado == EstadoEnvioEnum.ERROR
    assert out.intentos == 1
    assert "422" in out.error
    sleep.assert_not_awaited()  # 4xx no reintentable → sin espera


@pytest.mark.asyncio
async def test_enviar_uno_agota_reintentos_en_5xx():
    service = _service()
    service._post_resend = AsyncMock(return_value=(503, _resp(503, {"message": "down"})))
    sleep = AsyncMock()

    log = _log()
    out = await service.enviar_uno(
        log, html="x", client=MagicMock(), sleep=sleep, max_intentos=3
    )

    assert out.estado == EstadoEnvioEnum.ERROR
    assert out.intentos == 3
    assert sleep.await_count == 2  # backoff entre los 3 intentos


@pytest.mark.asyncio
async def test_enviar_uno_idempotente_si_ya_enviado():
    service = _service()
    service._post_resend = AsyncMock()

    log = _log(estado=EstadoEnvioEnum.ENVIADO)
    out = await service.enviar_uno(log, html="x", client=MagicMock(), sleep=AsyncMock())

    assert out.estado == EstadoEnvioEnum.ENVIADO
    service._post_resend.assert_not_awaited()  # no reenvía


@pytest.mark.asyncio
async def test_enviar_uno_sin_api_key_marca_error_sin_postear():
    service = _service(api_key="")
    service._post_resend = AsyncMock()

    log = _log()
    out = await service.enviar_uno(log, html="x", client=MagicMock(), sleep=AsyncMock())

    assert out.estado == EstadoEnvioEnum.ERROR
    assert "RESEND_API_KEY" in out.error
    service._post_resend.assert_not_awaited()


def test_payload_incluye_attachments_en_base64():
    service = _service()
    log = _log()
    contenido = b"%PDF-1.4 fake"
    payload = service._payload(
        log, "<b>x</b>", "onboarding@resend.dev", [("reporte.pdf", contenido)]
    )

    assert payload["from"] == "onboarding@resend.dev"
    assert payload["to"] == ["alumno@x.com"]
    assert payload["subject"] == "Tus actividades faltantes"
    assert payload["attachments"][0]["filename"] == "reporte.pdf"
    assert payload["attachments"][0]["content"] == base64.b64encode(contenido).decode("ascii")
