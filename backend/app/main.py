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
    # TODO: Inicializar conexion a BD
    # TODO: Verificar conectividad con N8N
    yield
    # Shutdown
    # TODO: Cerrar conexiones


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

    # TODO: Fase 1 - Agregar auth_router
    # from app.api.v1.routers import auth_router
    # app.include_router(auth_router.router, prefix="/api/v1", tags=["Auth"])

    # TODO: Fase 2 - Agregar routers de CRUD basico
    # from app.api.v1.routers import user_router, materia_router, comision_router
    # app.include_router(user_router.router, prefix="/api/v1", tags=["Usuarios"])
    # app.include_router(materia_router.router, prefix="/api/v1", tags=["Materias"])
    # app.include_router(comision_router.router, prefix="/api/v1", tags=["Comisiones"])

    # TODO: Fase 3 - Agregar routers de rubricas y entregas
    # from app.api.v1.routers import rubrica_router, entrega_router
    # app.include_router(rubrica_router.router, prefix="/api/v1", tags=["Rubricas"])
    # app.include_router(entrega_router.router, prefix="/api/v1", tags=["Entregas"])

    # TODO: Fase 4 - Agregar routers de correcciones y documentos
    # from app.api.v1.routers import correccion_router, documento_router
    # app.include_router(correccion_router.router, prefix="/api/v1", tags=["Correcciones"])
    # app.include_router(documento_router.router, prefix="/api/v1", tags=["Documentos"])


# Crear instancia de la aplicacion
app = create_application()
