# app/routers/dashboard_gestores.py
"""
Router del Dashboard de Gestores: config del cron + disparo manual de snapshots.

Las lecturas del dashboard (pie/detalle/tendencia) se agregan en T7.
Ref: PLAN_DASHBOARD_GESTORES.md §7, §8 (T6).
"""

import asyncio
import io
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import ContextoUniversidad, get_current_user, get_db, get_universidad_activa
from app.core.permissions import require_admin, require_gestor_or_admin
from app.core.scheduler import reprogramar_desde_config
from app.models import Usuario
from app.models.enums import EstadoAvanceEnum, OrigenSnapshotEnum
from app.schemas.dashboard_gestores import (
    AlumnoDetalle,
    AvanceResponse,
    CohorteArbol,
    CronConfigResponse,
    CronConfigUpdate,
    MateriaConfiguradaItem,
    SnapshotResumenResponse,
)
from app.services.dashboard_lectura_service import DashboardLecturaService
from app.services.snapshot_config_service import SnapshotConfigService
from app.services.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gestion/dashboard", tags=["dashboard-gestores"])

_SIN_CREDENCIALES = "Configurá tus credenciales de Moodle en tu perfil"


# ===================== Config del cron (admin) =====================


@router.get("/cron-config", response_model=CronConfigResponse)
async def obtener_cron_config(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CronConfigResponse:
    """Config actual del cron de snapshots. Solo admin."""
    require_admin(ctx)
    return await SnapshotConfigService(db).obtener()


@router.put("/cron-config", response_model=CronConfigResponse)
async def actualizar_cron_config(
    data: CronConfigUpdate,
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> CronConfigResponse:
    """Actualiza usuario/hora/activo del cron y lo reprograma en caliente. Solo admin."""
    require_admin(ctx)
    result = await SnapshotConfigService(db).actualizar(data)
    await reprogramar_desde_config()
    return result


# ===================== Disparo manual (gestor/admin) =====================


@router.post("/snapshot", response_model=list[SnapshotResumenResponse])
async def disparar_snapshot_manual(
    materia_id: int | None = Query(
        None, description="Materia puntual; si se omite, todas las configuradas"
    ),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[SnapshotResumenResponse]:
    """Dispara el cálculo de snapshot a mano (botón de pruebas), con las credenciales
    Moodle del usuario actual. Gestor o admin."""
    require_gestor_or_admin(ctx)
    service = SnapshotService(db)

    if materia_id is not None:
        if not current_user.moodle_username or not current_user.moodle_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=_SIN_CREDENCIALES
            )
        snap = await service.generar(
            materia_id, usuario=current_user, origen=OrigenSnapshotEnum.MANUAL
        )
        return [snap]

    try:
        return await service.generar_todas_para_usuario(
            current_user.id, origen=OrigenSnapshotEnum.MANUAL
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=_SIN_CREDENCIALES
        )


@router.get("/materias-configuradas", response_model=list[MateriaConfiguradaItem])
async def listar_materias_configuradas(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[MateriaConfiguradaItem]:
    """Materias listas para snapshot (con fecha de su último snapshot). Gestor o admin."""
    require_gestor_or_admin(ctx)
    return await DashboardLecturaService(db).materias_configuradas()


# ===================== Disparo manual con progreso en vivo (SSE) =====================


@router.get("/snapshot/stream")
async def snapshot_stream(
    materia_ids: list[int] | None = Query(
        None, description="Materias a generar; omitir = todas las configuradas"
    ),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> StreamingResponse:
    """Genera snapshots emitiendo el progreso por SSE (X/total alumnos), en vivo.

    Corre con las credenciales del usuario actual. Eventos:
    `{tipo: 'progreso', materia_idx, materias_total, procesados, total}` por alumno,
    `{tipo: 'done', materias}` al final, `{tipo: 'error', detalle}` si falla.
    """
    require_gestor_or_admin(ctx)
    service = SnapshotService(db)
    try:
        _, host = await service.token_de_usuario(current_user)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY, detail=_SIN_CREDENCIALES
        )

    if materia_ids:
        ids = materia_ids
    else:
        materias = await service.materia_repo.get_configuradas_dashboard()
        ids = [m.id for m in materias]

    async def event_gen():
        queue: asyncio.Queue = asyncio.Queue()

        async def run():
            # UNA sola sesión web para todas las materias del stream (no re-loguear).
            sesion = service.moodle.crear_cliente_sesion()
            try:
                await service.moodle.login_sesion(
                    sesion, host,
                    current_user.moodle_username, current_user.moodle_password_encrypted,
                )
                for idx, mid in enumerate(ids):
                    def on_progress(p: int, t: int, _idx: int = idx, _mid: int = mid):
                        queue.put_nowait(
                            {
                                "tipo": "progreso",
                                "materia_id": _mid,
                                "materia_idx": _idx + 1,
                                "materias_total": len(ids),
                                "procesados": p,
                                "total": t,
                            }
                        )

                    await service.generar(
                        mid,
                        usuario=current_user,
                        origen=OrigenSnapshotEnum.MANUAL,
                        on_progress=on_progress,
                        sesion=sesion,
                    )
                queue.put_nowait({"tipo": "done", "materias": len(ids)})
            except Exception as e:  # noqa: BLE001
                logger.exception("Snapshot stream falló")
                queue.put_nowait({"tipo": "error", "detalle": str(e)})
            finally:
                await sesion.aclose()
                queue.put_nowait(None)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ===================== Lectura del dashboard (gestor/admin) =====================


@router.get("/arbol", response_model=list[CohorteArbol])
async def obtener_arbol(
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[CohorteArbol]:
    """Árbol cohorte → cuatrimestre → materias para los selectores. Gestor o admin."""
    require_gestor_or_admin(ctx)
    return await DashboardLecturaService(db).obtener_arbol()


@router.get("/avance", response_model=AvanceResponse)
async def obtener_avance(
    cuatrimestre_id: int = Query(..., description="Cuatrimestre seleccionado"),
    materia_id: int | None = Query(None, description="Materia puntual; omitir = todas (Todos)"),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> AvanceResponse:
    """Conteos por estado del último snapshot + título dinámico (gráfico de torta)."""
    require_gestor_or_admin(ctx)
    return await DashboardLecturaService(db).avance(cuatrimestre_id, materia_id)


@router.get("/avance/detalle", response_model=list[AlumnoDetalle])
async def obtener_detalle(
    cuatrimestre_id: int = Query(...),
    estado: EstadoAvanceEnum = Query(..., description="Estado de la porción clickeada"),
    materia_id: int | None = Query(None),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> list[AlumnoDetalle]:
    """Lista de alumnos en un estado (alimenta el modal de detalle). Gestor o admin."""
    require_gestor_or_admin(ctx)
    return await DashboardLecturaService(db).detalle(cuatrimestre_id, estado, materia_id)


@router.get("/avance/excel")
async def descargar_avance_excel(
    cuatrimestre_id: int = Query(...),
    materia_id: int | None = Query(None),
    current_user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    ctx: ContextoUniversidad = Depends(get_universidad_activa),
) -> StreamingResponse:
    """Excel del avance: hoja Resumen (torta + conteos) + 1 hoja por estado. Gestor o admin."""
    require_gestor_or_admin(ctx)
    contenido, filename = await DashboardLecturaService(db).avance_excel(
        cuatrimestre_id, materia_id
    )
    return StreamingResponse(
        io.BytesIO(contenido),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
