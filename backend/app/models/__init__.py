# SQLAlchemy Models
"""
Models package - SQLAlchemy ORM models.

All models inherit from Base and use the mixins for common columns.
"""

from app.models.base import (
    Base,
    SoftDeleteMixin,
    TimestampMixin,
    async_session_maker,
    engine,
    get_async_session,
)
from app.models.enums import (
    EstadoCriterioEnum,
    EstadoEntregaEnum,
    FuenteRubricaEnum,
    RolEnum,
    TipoRubricaEnum,
)
from app.models.usuario import Usuario
from app.models.materia import CoordinadorMateria, Materia
from app.models.comision import Comision, ComisionTutor
from app.models.rubrica import Rubrica
from app.models.entrega import Entrega, EntregaHistorial
from app.models.correccion import Correccion

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    "engine",
    "async_session_maker",
    "get_async_session",
    # Enums
    "RolEnum",
    "TipoRubricaEnum",
    "EstadoEntregaEnum",
    "FuenteRubricaEnum",
    "EstadoCriterioEnum",
    # Models
    "Usuario",
    "Materia",
    "CoordinadorMateria",
    "Comision",
    "ComisionTutor",
    "Rubrica",
    "Entrega",
    "EntregaHistorial",
    "Correccion",
]
