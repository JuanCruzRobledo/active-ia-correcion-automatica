# app/main.py
"""
Entry point de la aplicacion FastAPI.

Ref: docs/specs/05-ARQUITECTURA-STACK.md seccion 3
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Gestiona el ciclo de vida de la aplicacion.

    Se ejecuta al iniciar y al cerrar la aplicacion.
    Util para:
    - Inicializar conexiones a BD
    - Inicializar servicios externos
    - Cerrar conexiones al shutdown
    """
    # Startup
    import logging

    from app.core.scheduler import (
        reprogramar_desde_config,
        reprogramar_notificaciones_desde_config,
        shutdown_scheduler,
        start_scheduler,
    )

    try:
        start_scheduler()
        await reprogramar_desde_config()
        await reprogramar_notificaciones_desde_config()
    except Exception:  # noqa: BLE001 — el scheduler no debe impedir el arranque de la app
        logging.getLogger(__name__).exception("No se pudo iniciar el scheduler")

    yield

    # Shutdown
    try:
        shutdown_scheduler()
    except Exception:  # noqa: BLE001
        pass


def create_application() -> FastAPI:
    """
    Factory function para crear la instancia de FastAPI.

    Permite crear multiples instancias (util para testing).
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Plataforma de correccion automatica de trabajos practicos con IA",
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Configurar CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
        expose_headers=["Content-Disposition"],  # Permite que el frontend lea este header
    )

    # Registrar routers
    register_routers(app)

    return app


def register_routers(app: FastAPI) -> None:
    """
    Registra todos los routers de la API.

    Los routers se agregaran en fases posteriores:
    - Fase 1: auth
    - Fase 2: usuarios, materias, comisiones
    - Fase 3: rubricas, entregas
    - Fase 4: correcciones, documentos
    """
    # Health check endpoint (no necesita router)
    @app.get(
        "/api/v1/health",
        tags=["Health"],
        summary="Verificar estado del servicio",
    )
    async def health_check():
        """
        Endpoint para verificar que el servicio esta funcionando.

        Retorna estado basico del servicio.
        En futuras versiones puede incluir:
        - Estado de conexion a BD
        - Estado de conexion a N8N
        - Metricas basicas
        """
        return {
            "status": "healthy",
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # Fase 1 - Auth router
    from app.routers.auth import router as auth_router

    app.include_router(auth_router, prefix="/api/v1")

    # Fase 2 - CRUD basico
    from app.routers.usuarios import router as usuarios_router

    app.include_router(usuarios_router, prefix="/api/v1")

    # Fase 2 - Materias router
    from app.routers.materias import router as materias_router

    app.include_router(materias_router, prefix="/api/v1")

    # Fase 2 - Comisiones router
    from app.routers.comisiones import router as comisiones_router

    app.include_router(comisiones_router, prefix="/api/v1")

    # Fase 3 - Rubricas router
    from app.routers.rubricas import router as rubricas_router

    app.include_router(rubricas_router, prefix="/api/v1")

    # Fase 3 - Entregas router
    from app.routers.entregas import router as entregas_router

    app.include_router(entregas_router, prefix="/api/v1")

    # Fase 4 - Correcciones router
    from app.routers.correcciones import router as correcciones_router

    app.include_router(correcciones_router, prefix="/api/v1")

    # Fase 4 - Documentos router
    from app.routers.documentos import router as documentos_router

    app.include_router(documentos_router, prefix="/api/v1")

    # Fase 6 - Dashboard router
    from app.routers.dashboard import router as dashboard_router

    app.include_router(dashboard_router, prefix="/api/v1/dashboard", tags=["Dashboard"])

    # Fase 6 - Perfil router
    from app.routers.perfil import router as perfil_router

    app.include_router(perfil_router, prefix="/api/v1")

    # Fase 6 - Actividades router (audit log)
    from app.routers.actividades import router as actividades_router

    app.include_router(actividades_router, prefix="/api/v1")

    # Moodle pendientes
    from app.routers.pendientes import router as pendientes_router

    app.include_router(pendientes_router, prefix="/api/v1")

    # Moodle import (Fase 2 — importar entregas desde Moodle)
    from app.routers.moodle_import import router as moodle_import_router

    app.include_router(moodle_import_router, prefix="/api/v1")

    # Por entregar (correcciones pendientes de subir a Moodle)
    from app.routers.por_entregar import router as por_entregar_router

    app.include_router(por_entregar_router, prefix="/api/v1")

    # Sync (tokens de versión para el banner "hay novedades")
    from app.routers.sync import router as sync_router

    app.include_router(sync_router, prefix="/api/v1")

    # Gestión (rol GESTOR — reportes/export de usuarios de Moodle)
    from app.routers.gestion import router as gestion_router

    app.include_router(gestion_router, prefix="/api/v1")

    # Cohortes/Cuatrimestres (ABM admin — Dashboard de Gestores)
    from app.routers.cohortes import router as cohortes_router

    app.include_router(cohortes_router, prefix="/api/v1")

    # Unidades + config de dashboard de la materia (ABM admin — Dashboard de Gestores)
    from app.routers.unidades import router as unidades_router

    app.include_router(unidades_router, prefix="/api/v1")

    # Exámenes de la materia (ABM admin — seguimiento de evaluaciones)
    from app.routers.examenes import router as examenes_router

    app.include_router(examenes_router, prefix="/api/v1")

    # Dashboard de Gestores — config del cron + disparo manual de snapshots
    from app.routers.dashboard_gestores import router as dashboard_gestores_router

    app.include_router(dashboard_gestores_router, prefix="/api/v1")

    # Notificaciones por email — ABM de tutores nexo (admin)
    from app.routers.tutores_nexo import router as tutores_nexo_router

    app.include_router(tutores_nexo_router, prefix="/api/v1")

    # Notificaciones por email — cron-config, disparo, prueba, historial, preview (admin)
    from app.routers.notificaciones import router as notificaciones_router

    app.include_router(notificaciones_router, prefix="/api/v1")

    # Cierre de cursada (admin panel) — mapeo de ítems del calificador + corridas
    from app.routers.cierre_cursada import router as cierre_cursada_router

    app.include_router(cierre_cursada_router, prefix="/api/v1")

    # Público (Fase 3 — PDF de devolución sin JWT, vía token firmado)
    from app.routers.public_docs import router as public_docs_router

    app.include_router(public_docs_router, prefix="/api/v1")


# Crear instancia de la aplicacion
app = create_application()
