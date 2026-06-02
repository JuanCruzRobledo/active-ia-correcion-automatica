"""Schemas de la pantalla "Gestión" (rol GESTOR).

Request de filtros (con validación) + responses (cursos, opciones de filtro, alumnos).
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator

from app.services.gestion_inactividad import RANGO, TIPOS_VALIDOS

ROLES_VALIDOS = {"student", "editingteacher", "teacher"}
ESTATUS_VALIDOS = {"activo", "inactivo"}


class CursoGestionResponse(BaseModel):
    materia_id: int
    nombre: str
    codigo: str
    moodle_course_id: int


class OpcionCatalogo(BaseModel):
    value: str
    label: str


class FiltrosDisponiblesResponse(BaseModel):
    regionales: list[str]
    comisiones: list[str]
    roles: list[OpcionCatalogo]
    estatus: list[OpcionCatalogo]
    inactividad: list[OpcionCatalogo]


class FiltrosGestionRequest(BaseModel):
    rol: Optional[str] = None              # 'student' | 'editingteacher' | 'teacher' | null (todos)
    estatus: Optional[str] = None          # 'activo' | 'inactivo' | null (todos)
    regionales: list[str] = Field(default_factory=list)   # vacío = todas
    comisiones: list[str] = Field(default_factory=list)    # vacío = todas
    inactividad_tipo: Optional[str] = None  # clave de banda, 'rango', 'nunca' | null (sin filtro)
    inactividad_desde: Optional[int] = None
    inactividad_hasta: Optional[int] = None

    @model_validator(mode="after")
    def _validar(self):
        if self.rol is not None and self.rol not in ROLES_VALIDOS:
            raise ValueError(f"rol inválido: {self.rol}")
        if self.estatus is not None and self.estatus not in ESTATUS_VALIDOS:
            raise ValueError(f"estatus inválido: {self.estatus}")
        if self.inactividad_tipo is not None and self.inactividad_tipo not in TIPOS_VALIDOS:
            raise ValueError(f"inactividad_tipo inválido: {self.inactividad_tipo}")
        if self.inactividad_tipo == RANGO:
            if self.inactividad_desde is None or self.inactividad_hasta is None:
                raise ValueError("El rango de inactividad requiere 'desde' y 'hasta'")
            if self.inactividad_desde < 0 or self.inactividad_hasta < self.inactividad_desde:
                raise ValueError("Rango inválido: se requiere 0 <= desde <= hasta")
        return self


class AlumnoGestionResponse(BaseModel):
    nombre: str
    apellido: str
    email: str
    regional: str
    comision: str
    dias_inactividad: Optional[int] = None
    tiempo_inactividad: str
    suspendido: bool


class ConsultaGestionResponse(BaseModel):
    items: list[AlumnoGestionResponse]
    total: int
