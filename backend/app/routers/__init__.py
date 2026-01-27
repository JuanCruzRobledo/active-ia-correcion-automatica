# Presentation Layer - Routers
"""
Routers package - FastAPI routers for HTTP endpoints.

Each router handles a specific domain and uses services for business logic.
"""

from app.routers.auth import router as auth_router
from app.routers.comisiones import router as comisiones_router
from app.routers.correcciones import router as correcciones_router
from app.routers.documentos import router as documentos_router
from app.routers.entregas import router as entregas_router
from app.routers.materias import router as materias_router
from app.routers.rubricas import router as rubricas_router
from app.routers.usuarios import router as usuarios_router

__all__ = [
    "auth_router",
    "usuarios_router",
    "materias_router",
    "comisiones_router",
    "rubricas_router",
    "entregas_router",
    "correcciones_router",
    "documentos_router",
]
