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
    CategoriaItemCierreEnum,
    EstadoAvanceEnum,
    EstadoCierreEnum,
    EstadoCriterioEnum,
    EstadoEntregaEnum,
    EstadoEnvioEnum,
    FuenteComponenteEnum,
    FuenteRubricaEnum,
    ModoAprobacionEnum,
    MoodleSyncEstado,
    OrigenSnapshotEnum,
    RolEnum,
    TipoActividadEnum,
    TipoComponenteEnum,
    TipoExamenEnum,
    TipoNotificacionEnum,
    TipoRubricaEnum,
)
from app.models.usuario import Usuario
from app.models.universidad import Universidad
from app.models.usuario_universidad import UsuarioUniversidad
from app.models.cohorte import Cohorte, Cuatrimestre
from app.models.materia import CoordinadorMateria, Materia
from app.models.unidad import Unidad
from app.models.componente_unidad import ComponenteUnidad
from app.models.examen_materia import ExamenMateria
from app.models.comision import Comision, ComisionTutor
from app.models.rubrica import Rubrica
from app.models.entrega import Entrega, EntregaHistorial
from app.models.correccion import Correccion, CorreccionHistorial
from app.models.actividad import Actividad
from app.models.moodle_sync import MoodleSync
from app.models.avance import AvanceAlumno, AvanceSnapshot, SnapshotCronConfig
from app.models.tutor_nexo import TutorNexo
from app.models.notificacion import EnvioEmailLog, NotificacionCronConfig
from app.models.cierre_cursada import CierreCursadaAlumno, CierreCursadaRun

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
    "TipoActividadEnum",
    "MoodleSyncEstado",
    "EstadoAvanceEnum",
    "OrigenSnapshotEnum",
    "TipoNotificacionEnum",
    "EstadoEnvioEnum",
    "TipoComponenteEnum",
    "FuenteComponenteEnum",
    "TipoExamenEnum",
    "ModoAprobacionEnum",
    "CategoriaItemCierreEnum",
    "EstadoCierreEnum",
    # Models
    "Usuario",
    "Universidad",
    "UsuarioUniversidad",
    "Cohorte",
    "Cuatrimestre",
    "Materia",
    "Unidad",
    "ComponenteUnidad",
    "ExamenMateria",
    "CoordinadorMateria",
    "Comision",
    "ComisionTutor",
    "Rubrica",
    "Entrega",
    "EntregaHistorial",
    "Correccion",
    "CorreccionHistorial",
    "Actividad",
    "MoodleSync",
    "AvanceSnapshot",
    "AvanceAlumno",
    "SnapshotCronConfig",
    "TutorNexo",
    "EnvioEmailLog",
    "NotificacionCronConfig",
    "CierreCursadaRun",
    "CierreCursadaAlumno",
]
