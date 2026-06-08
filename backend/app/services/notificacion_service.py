# app/services/notificacion_service.py
"""
NotificacionService — orquesta la corrida semanal de notificaciones por email.

ejecutar_corrida_semanal:
  1. (opcional) refresca los snapshots de avance con las credenciales del usuario de servicio.
  2. arma los destinatarios (alumnos / tutores académicos / tutores nexo) cruzando
     los últimos snapshots (notificacion_agg).
  3. renderiza (HTML / PDF / Excel) y encola+envía vía EmailService, registrando EnvioEmailLog.
  Idempotente por tanda_id: no reenvía refs ya ENVIADOS (reanudación).

Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.2.
"""

import logging
import uuid

import httpx

from app.core.config import get_settings
from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum
from app.models.notificacion import EnvioEmailLog
from app.repositories.avance_repository import AvanceRepository
from app.repositories.comision_repository import ComisionRepository
from app.repositories.materia_repository import MateriaRepository
from app.repositories.notificacion_repository import NotificacionRepository
from app.repositories.tutor_nexo_repository import TutorNexoRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.email_service import EmailService
from app.services.notificacion_config_service import NotificacionConfigService
from app.services.notificacion_agg import (
    construir_destinatarios_alumnos,
    construir_destinatarios_tutores_academicos,
    construir_destinatarios_tutores_nexo,
    numero_comision,
)
from app.services.notificacion_render import (
    construir_excel_tutor_nexo,
    construir_html_alumno,
    construir_pdf_tutor_academico,
)
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)


def _cuerpo_adjunto(nombre: str, intro: str) -> str:
    """HTML simple para los emails con adjunto (tutor académico / nexo)."""
    saludo = f"Hola {nombre}," if nombre else "Hola,"
    return (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#333">'
        f"<p>{saludo}</p><p>{intro}</p>"
        '<p style="color:#666;font-size:12px">Active-IA · notificación automática</p></div>'
    )


class NotificacionService:
    """Orquestador de la corrida semanal de notificaciones."""

    def __init__(self, db):
        self.db = db
        self.avance_repo = AvanceRepository(db)
        self.materia_repo = MateriaRepository(db)
        self.comision_repo = ComisionRepository(db)
        self.usuario_repo = UsuarioRepository(db)
        self.nexo_repo = TutorNexoRepository(db)
        self.notif_repo = NotificacionRepository(db)
        self.email_service = EmailService(db)
        self.snapshot_service = SnapshotService(db)
        self.config_service = NotificacionConfigService(db)
        self.settings = get_settings()

    # ---------- carga de datos ----------

    async def _cargar_avances_por_materia(self) -> list[dict]:
        """Por cada materia configurada con snapshot: {materia_id, materia, alumnos}."""
        materias = await self.materia_repo.get_configuradas_dashboard()
        out: list[dict] = []
        for m in materias:
            snap = await self.avance_repo.get_ultimo_snapshot(m.id)
            if snap is None:
                continue
            alumnos = await self.avance_repo.get_alumnos_de_snapshot(snap.id)
            out.append({"materia_id": m.id, "materia": m.nombre, "alumnos": alumnos})
        return out

    async def _cargar_tutores(self, mapa_materia: dict[int, str]) -> list[dict]:
        tutores = await self.usuario_repo.get_tutores()
        out: list[dict] = []
        for t in tutores:
            comisiones = await self.comision_repo.get_by_tutor(t.id)
            out.append(
                {
                    "email": t.email,
                    "nombre": t.nombre,
                    "comisiones": [
                        {
                            "materia_id": c.materia_id,
                            "materia": mapa_materia.get(c.materia_id, ""),
                            "numero": numero_comision(c.nombre),
                            "nombre": c.nombre,
                        }
                        for c in comisiones
                    ],
                }
            )
        return out

    # ---------- envío por tipo ----------

    def _nuevo_log(self, tanda_id, tipo, email, ref, asunto) -> EnvioEmailLog:
        return EnvioEmailLog(
            tanda_id=tanda_id,
            tipo=tipo,
            destinatario_email=email,
            destinatario_ref=str(ref),
            asunto=asunto,
            estado=EstadoEnvioEnum.PENDIENTE,
            intentos=0,
        )

    async def _enviar_alumnos(self, tanda_id, avances, client, remitente=None) -> int:
        dests = construir_destinatarios_alumnos(avances)
        ya = await self.notif_repo.refs_enviados(tanda_id, TipoNotificacionEnum.ALUMNO)
        items, logs = [], []
        for d in dests:
            if str(d["moodle_user_id"]) in ya:
                continue
            log = self._nuevo_log(
                tanda_id, TipoNotificacionEnum.ALUMNO, d["email"],
                d["moodle_user_id"], "Tus actividades pendientes — Active-IA",
            )
            html = construir_html_alumno(d["nombre"], d["filas"])
            logs.append(log)
            items.append({"log": log, "html": html, "remitente": remitente})
        if items:
            await self.email_service.enviar_lote(items, client=client)
            await self.notif_repo.agregar_todos(logs)
        return len(items)

    async def _enviar_tutores(
        self, tanda_id, tutores, avances, client, remitente=None, comisiones_objetivo=None
    ) -> int:
        dests = construir_destinatarios_tutores_academicos(
            tutores, avances, comisiones_objetivo
        )
        ya = await self.notif_repo.refs_enviados(tanda_id, TipoNotificacionEnum.TUTOR_ACADEMICO)
        items, logs = [], []
        for d in dests:
            if d["email"] in ya:
                continue
            log = self._nuevo_log(
                tanda_id, TipoNotificacionEnum.TUTOR_ACADEMICO, d["email"],
                d["email"], "Avance de tus comisiones — Active-IA",
            )
            pdf = construir_pdf_tutor_academico(d["nombre"], d["materias"])
            html = _cuerpo_adjunto(
                d["nombre"], "Adjuntamos el detalle de actividades faltantes de tus alumnos."
            )
            logs.append(log)
            items.append({
                "log": log, "html": html, "remitente": remitente,
                "attachments": [("actividades_faltantes.pdf", pdf)],
            })
        if items:
            await self.email_service.enviar_lote(items, client=client)
            await self.notif_repo.agregar_todos(logs)
        return len(items)

    async def _enviar_nexos(self, tanda_id, nexos, avances, client, remitente=None) -> int:
        dests = construir_destinatarios_tutores_nexo(nexos, avances)
        ya = await self.notif_repo.refs_enviados(tanda_id, TipoNotificacionEnum.TUTOR_NEXO)
        items, logs = [], []
        for d in dests:
            if d["regional"] in ya:
                continue
            log = self._nuevo_log(
                tanda_id, TipoNotificacionEnum.TUTOR_NEXO, d["email"],
                d["regional"], f"Avance regional {d['regional']} — Active-IA",
            )
            xlsx = construir_excel_tutor_nexo(d["regional"], d["materias"])
            html = _cuerpo_adjunto(
                d["nombre"], f"Adjuntamos el avance de los alumnos de la regional {d['regional']}."
            )
            nombre_archivo = f"avance_{d['regional']}.xlsx".replace(" ", "_")
            logs.append(log)
            items.append({
                "log": log, "html": html, "remitente": remitente,
                "attachments": [(nombre_archivo, xlsx)],
            })
        if items:
            await self.email_service.enviar_lote(items, client=client)
            await self.notif_repo.agregar_todos(logs)
        return len(items)

    # ---------- corrida ----------

    async def ejecutar_corrida_semanal(
        self,
        usuario_id: int,
        *,
        refrescar: bool = True,
        tanda_id: str | None = None,
        incluir_alumnos: bool = True,
        incluir_tutores: bool = True,
        incluir_nexos: bool = True,
        comisiones_objetivo: set[tuple[int, int]] | None = None,
    ) -> dict:
        """Corre la cadena: refresca snapshots → alumnos → tutores → nexos.

        Flags de modo prueba (QA):
        - incluir_alumnos/tutores/nexos: permite apagar un tipo de destinatario.
        - comisiones_objetivo: set de (materia_id, numero) para mandar SOLO a esos
          tutores (None = todas las comisiones).

        Devuelve {tanda_id, alumnos, tutores, nexos} con la cantidad enviada por tipo.
        """
        tanda_id = tanda_id or uuid.uuid4().hex
        if refrescar:
            await self.snapshot_service.generar_todas_para_usuario(usuario_id)

        config = await self.config_service.get_config()
        remitente = config.remitente or None

        avances = await self._cargar_avances_por_materia()
        mapa_materia = {a["materia_id"]: a["materia"] for a in avances}
        tutores = await self._cargar_tutores(mapa_materia) if incluir_tutores else []
        nexos = (
            [
                {"email": n.email, "nombre": n.nombre, "regional": n.regional}
                for n in await self.nexo_repo.get_activos()
            ]
            if incluir_nexos
            else []
        )

        resumen = {"tanda_id": tanda_id, "alumnos": 0, "tutores": 0, "nexos": 0}
        async with httpx.AsyncClient(timeout=30.0) as client:
            if incluir_alumnos:
                resumen["alumnos"] = await self._enviar_alumnos(tanda_id, avances, client, remitente)
            if incluir_tutores:
                resumen["tutores"] = await self._enviar_tutores(
                    tanda_id, tutores, avances, client, remitente, comisiones_objetivo
                )
            if incluir_nexos:
                resumen["nexos"] = await self._enviar_nexos(tanda_id, nexos, avances, client, remitente)

        logger.info("Corrida notificaciones %s: %s", tanda_id, resumen)
        return resumen
