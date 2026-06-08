# app/services/email_service.py
"""
EmailService — envío de emails de notificación vía Resend (PLAN_NOTIFICACIONES_EMAIL.md §5.2, §7).

Diseño desacoplado de la DB: `enviar_uno` recibe un EnvioEmailLog ya creado y lo
MUTA (estado/resend_id/error/intentos/enviado_en); el caller (NotificacionService)
es quien lo persiste. El POST a Resend va por httpx (sin dependencia nueva; mismo
canal validado en el spike T0). Reintentos con backoff ante 429/5xx; los 4xx no se
reintentan. `enviar_lote` aplica throttle (EMAIL_RATE_POR_SEGUNDO).
"""

import asyncio
import base64
import logging
from datetime import datetime
from typing import Awaitable, Callable, Iterable

import httpx

from app.core.config import get_settings
from app.models.enums import EstadoEnvioEnum
from app.models.notificacion import EnvioEmailLog

logger = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"
# Status HTTP transitorios que ameritan reintento (el resto de 4xx NO se reintenta).
_REINTENTABLES = {429, 500, 502, 503, 504}


class EmailService:
    """Envía emails vía Resend, registrando estado en cada EnvioEmailLog."""

    def __init__(self, db=None, *, settings=None):
        self.db = db
        self.settings = settings or get_settings()

    def _payload(
        self,
        log: EnvioEmailLog,
        html: str,
        remitente: str,
        attachments: list[tuple[str, bytes]] | None,
    ) -> dict:
        """Arma el body para la API de Resend. attachments: list[(filename, bytes)]."""
        payload: dict = {
            "from": remitente,
            "to": [log.destinatario_email],
            "subject": log.asunto or "",
            "html": html,
        }
        if attachments:
            payload["attachments"] = [
                {"filename": fn, "content": base64.b64encode(contenido).decode("ascii")}
                for fn, contenido in attachments
            ]
        return payload

    async def _post_resend(self, payload: dict, client: httpx.AsyncClient):
        """POST a Resend. Devuelve (status_code, response). Punto de mock en tests."""
        resp = await client.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self.settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        return resp.status_code, resp

    async def enviar_uno(
        self,
        log: EnvioEmailLog,
        *,
        html: str,
        client: httpx.AsyncClient,
        remitente: str | None = None,
        attachments: list[tuple[str, bytes]] | None = None,
        max_intentos: int = 3,
        backoff_base: float = 0.5,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> EnvioEmailLog:
        """Intenta enviar UN email y MUTA el log con el resultado. No persiste.

        Idempotente: si el log ya está ENVIADO, no hace nada. Si no hay API key,
        marca ERROR sin postear. Reintenta en 429/5xx con backoff exponencial.
        """
        if log.estado == EstadoEnvioEnum.ENVIADO:
            return log
        if not self.settings.RESEND_API_KEY:
            log.estado = EstadoEnvioEnum.ERROR
            log.error = "RESEND_API_KEY no configurada"
            return log

        remitente = remitente or self.settings.EMAIL_REMITENTE
        payload = self._payload(log, html, remitente, attachments)

        ultimo_error: str | None = None
        for intento in range(1, max_intentos + 1):
            log.intentos = intento
            try:
                status, resp = await self._post_resend(payload, client)
            except Exception as e:  # noqa: BLE001 — error de red: reintentable
                ultimo_error = f"red: {e}"
                if intento < max_intentos:
                    await sleep(backoff_base * (2 ** (intento - 1)))
                    continue
                break

            if status in (200, 201):
                try:
                    data = resp.json()
                except Exception:  # noqa: BLE001
                    data = {}
                log.estado = EstadoEnvioEnum.ENVIADO
                log.resend_id = (data or {}).get("id")
                log.error = None
                log.enviado_en = datetime.utcnow()
                return log

            # Respuesta de error
            try:
                detalle = resp.json()
            except Exception:  # noqa: BLE001
                detalle = getattr(resp, "text", "")
            ultimo_error = f"HTTP {status}: {detalle}"
            if status in _REINTENTABLES and intento < max_intentos:
                await sleep(backoff_base * (2 ** (intento - 1)))
                continue
            break  # 4xx no reintentable → cortar

        log.estado = EstadoEnvioEnum.ERROR
        log.error = (ultimo_error or "error desconocido")[:1000]
        return log

    async def enviar_lote(
        self,
        items: Iterable[dict],
        *,
        client: httpx.AsyncClient | None = None,
        max_intentos: int = 3,
    ) -> list[EnvioEmailLog]:
        """Envía una lista de items en serie con throttle (EMAIL_RATE_POR_SEGUNDO).

        Cada item: {"log": EnvioEmailLog, "html": str,
                    "attachments": list[(fn,bytes)]|None, "remitente": str|None}.
        Reusa un único cliente httpx (keep-alive); si no se pasa, crea y cierra uno.
        """
        rate = self.settings.EMAIL_RATE_POR_SEGUNDO or 0
        intervalo = 1.0 / rate if rate > 0 else 0.0
        items = list(items)
        resultados: list[EnvioEmailLog] = []

        propio = client is None
        if propio:
            client = httpx.AsyncClient(timeout=30.0)
        try:
            for i, it in enumerate(items):
                if i > 0 and intervalo:
                    await asyncio.sleep(intervalo)
                r = await self.enviar_uno(
                    it["log"],
                    html=it["html"],
                    client=client,
                    remitente=it.get("remitente"),
                    attachments=it.get("attachments"),
                    max_intentos=max_intentos,
                )
                resultados.append(r)
        finally:
            if propio:
                await client.aclose()
        return resultados
