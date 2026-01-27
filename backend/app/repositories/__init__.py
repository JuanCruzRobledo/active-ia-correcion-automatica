# Data Access Layer - Repositories
"""
Repositories package - Data access layer.

All repositories handle database operations only, no business logic.
"""

from app.repositories.comision_repository import (
    ComisionRepository,
    ComisionTutorRepository,
)
from app.repositories.correccion_repository import CorreccionRepository
from app.repositories.entrega_repository import EntregaRepository
from app.repositories.entrega_historial_repository import (
    EntregaHistorialRepository,
)
from app.repositories.materia_repository import (
    CoordinadorMateriaRepository,
    MateriaRepository,
)
from app.repositories.rubrica_repository import RubricaRepository
from app.repositories.usuario_repository import UsuarioRepository

__all__ = [
    "UsuarioRepository",
    "MateriaRepository",
    "CoordinadorMateriaRepository",
    "ComisionRepository",
    "ComisionTutorRepository",
    "RubricaRepository",
    "EntregaRepository",
    "EntregaHistorialRepository",
    "CorreccionRepository",
]
