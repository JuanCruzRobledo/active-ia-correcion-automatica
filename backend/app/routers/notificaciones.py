# app/routers/notificaciones.py
"""
Router de notificaciones por email (solo ADMIN).

- cron-config GET/PUT (+ reprograma el job semanal en caliente)
- disparar (corrida manual, para QA)
- enviar-prueba (un email de muestra a una casilla, valida el canal Resend)
- historial (auditoría de envíos)
- preview/{tipo} (HTML / PDF / Excel de muestra, sin enviar)

Ref: PLAN_NOTIFICACIONES_EMAIL.md §5.4 (T8).
"""

import io
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.core.permissions import require_admin
from app.core.scheduler import reprogramar_notificaciones_desde_config
from app.models import Usuario
from app.models.enums import EstadoEnvioEnum, TipoNotificacionEnum
from app.models.notificacion import EnvioEmailLog
from app.repositories.notificacion_repository import NotificacionRepository
from app.schemas.notificacion import (
    CorridaResumenResponse,
    EnviarPruebaRequest,
    EnvioEmailLogResponse,
    NotifCronConfigResponse,
    NotifCronConfigUpdate,
)
from app.services.email_service import EmailService
from app.services.notificacion_config_service import NotificacionConfigService
from app.services.notificacion_render import (
    construir_excel_avance,
    construir_html_alumno,
)
from app.services.notificacion_service import NotificacionService

router = APIRouter(prefix="/notificaciones", tags=["notificaciones"])


# ----- datos de muestra para preview / prueba -----

def _filas_muestra_alumno() -> list[dict]:
    return [
        {"comision": "M26 C1-09", "materia": "Programación 1", "actividad": "Falta Unidad 4 y 5"},
        {"comision": "M26 C1-01", "materia": "Organización Empresarial",
         "actividad": "Actividad de Cierre unidad 8"},
    ]


def _materias_muestra_tutor() -> list[dict]:
    return [{
        "materia": "Programación 1", "etiqueta": "Unidad",
        "alumnos": [
            {"comision": "M26 C1-09", "apellido": "Gómez", "nombre": "Ana", "deudas": [
                {"unidad": 4, "tipo": "TP", "estado": "no entregado"},
                {"unidad": 5, "tipo": "CIERRE", "estado": "pendiente"},
            ]},
            {"comision": "M26 C1-10", "apellido": "Díaz", "nombre": "Carla", "deudas": [
                {"unidad": 3, "tipo": "QUIZ", "estado": "desaprobado"},
            ]},
        ],
    }]


def _materias_muestra_nexo() -> list[dict]:
    return [{
        "materia": "Programación 1", "etiqueta": "Unidad",
        "alumnos": [
            {"comision": "M26 C1-09", "apellido": "Gómez", "nombre": "Ana", "deudas": [
                {"unidad": 4, "tipo": "TP", "estado": "no entregado"},
                {"unidad": 5, "tipo": "CIERRE", "estado": "pendiente"},
            ]},
            {"comision": "M26 C1-01", "apellido": "Ruiz", "nombre": "Eva", "deudas": [
                {"unidad": 2, "tipo": "AUTOEVALUACION", "estado": "pendiente"},
            ]},
        ],
    }]


# ===================== cron-config =====================


@router.get("/cron-config", response_model=NotifCronConfigResponse)
async def obtener_cron_config(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotifCronConfigResponse:
    require_admin(current_user)
    return await NotificacionConfigService(db).obtener()


@router.put("/cron-config", response_model=NotifCronConfigResponse)
async def actualizar_cron_config(
    data: NotifCronConfigUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotifCronConfigResponse:
    require_admin(current_user)
    result = await NotificacionConfigService(db).actualizar(data)
    await reprogramar_notificaciones_desde_config()
    return result


# ===================== disparo manual (QA) =====================


@router.post("/disparar", response_model=CorridaResumenResponse)
async def disparar_corrida(
    refrescar: bool = Query(
        False, description="Si True, regenera snapshots antes de enviar (lento)."
    ),
    incluir_alumnos: bool = Query(
        True, description="Fase de prueba: poné False para NO mandar a los alumnos."
    ),
    incluir_tutores: bool = Query(True),
    incluir_nexos: bool = Query(True),
    comisiones: list[str] | None = Query(
        None,
        description='Filtro QA de tutores: "materia_id:numero" (ej 7:1). Vacío = todas.',
    ),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CorridaResumenResponse:
    """Corre la cadena de notificaciones a mano (QA). Usa el usuario del cron-config
    (o el actual si no hay) para refrescar snapshots. Solo admin.

    En fase de prueba: `incluir_alumnos=false` + `comisiones=7:1&comisiones=7:2…`
    para mandar solo a los tutores de esas comisiones (y a los nexos)."""
    require_admin(current_user)
    config = await NotificacionConfigService(db).get_config()
    usuario_id = config.usuario_id or current_user.id

    objetivo: set[tuple[int, int]] | None = None
    if comisiones:
        objetivo = set()
        for c in comisiones:
            try:
                mid, num = c.split(":")
                objetivo.add((int(mid), int(num)))
            except (ValueError, AttributeError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Comisión inválida '{c}': usá el formato materia_id:numero (ej 7:1)",
                )

    resumen = await NotificacionService(db).ejecutar_corrida_semanal(
        usuario_id,
        refrescar=refrescar,
        incluir_alumnos=incluir_alumnos,
        incluir_tutores=incluir_tutores,
        incluir_nexos=incluir_nexos,
        comisiones_objetivo=objetivo,
        manual=True,
    )
    return CorridaResumenResponse(**resumen)


# ===================== enviar prueba =====================


@router.post("/enviar-prueba", response_model=EnvioEmailLogResponse)
async def enviar_prueba(
    data: EnviarPruebaRequest,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EnvioEmailLogResponse:
    """Envía un email de muestra (tabla del alumno) a la casilla indicada. Solo admin."""
    require_admin(current_user)
    log = EnvioEmailLog(
        tanda_id=f"prueba-{uuid.uuid4().hex[:8]}",
        tipo=TipoNotificacionEnum.ALUMNO,
        destinatario_email=data.email,
        destinatario_ref="prueba",
        asunto="Prueba de notificaciones — Active-IA",
        estado=EstadoEnvioEnum.PENDIENTE,
        intentos=0,
    )
    html = construir_html_alumno("Equipo Active-IA", _filas_muestra_alumno())
    config = await NotificacionConfigService(db).get_config()
    email_service = EmailService(db)
    async with httpx.AsyncClient(timeout=30.0) as client:
        await email_service.enviar_uno(
            log, html=html, client=client, remitente=config.remitente or None
        )
    await NotificacionRepository(db).agregar_todos([log])
    return EnvioEmailLogResponse.model_validate(log)


# ===================== historial =====================


@router.get("/historial", response_model=list[EnvioEmailLogResponse])
async def historial(
    tanda_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[EnvioEmailLogResponse]:
    require_admin(current_user)
    logs = await NotificacionRepository(db).listar(tanda_id=tanda_id, limit=limit)
    return [EnvioEmailLogResponse.model_validate(x) for x in logs]


# ===================== preview (sin enviar) =====================


@router.get("/preview/{tipo}")
async def preview(
    tipo: str,
    current_user: Usuario = Depends(get_current_user),
):
    """Devuelve una muestra del formato sin enviar nada: alumno=HTML, tutor/nexo=Excel."""
    require_admin(current_user)
    _XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if tipo == "alumno":
        return HTMLResponse(construir_html_alumno("Alumno de prueba", _filas_muestra_alumno()))
    if tipo == "tutor":
        # Tutor académico: 2 hojas por materia (por unidad + por comisión).
        xlsx = construir_excel_avance(_materias_muestra_tutor(), agrupar="ambos")
        return StreamingResponse(
            io.BytesIO(xlsx), media_type=_XLSX,
            headers={"Content-Disposition": 'attachment; filename="preview_tutor.xlsx"'},
        )
    if tipo == "nexo":
        # Tutor nexo: Excel agrupado por unidad/semana.
        xlsx = construir_excel_avance(_materias_muestra_nexo(), agrupar="unidad")
        return StreamingResponse(
            io.BytesIO(xlsx), media_type=_XLSX,
            headers={"Content-Disposition": 'attachment; filename="preview_nexo.xlsx"'},
        )
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="tipo debe ser 'alumno', 'tutor' o 'nexo'",
    )
