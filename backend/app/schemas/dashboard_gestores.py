# app/schemas/dashboard_gestores.py
"""
Schemas del Dashboard de Gestores: config del cron + resumen de snapshot.

Ref: PLAN_DASHBOARD_GESTORES.md §7, §8 (T6). Las lecturas (pie/detalle/tendencia)
se agregan en T7.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EstadoAvanceEnum, OrigenSnapshotEnum


class CronConfigUpdate(BaseModel):
    """Config editable del cron de snapshots (desde el admin panel)."""

    usuario_id: int | None = Field(
        None, description="Usuario cuyas credenciales Moodle usa el cron (null = sin asignar)"
    )
    # Fase 3 multi-tenant (OQ2): universidad activa del cron (sin JWT/ctx). Se
    # exige junto con usuario_id al activar (SnapshotConfigService.actualizar).
    universidad_id: int | None = Field(
        None, description="Universidad activa para el cron (null = sin asignar)"
    )
    hora: int = Field(..., ge=0, le=23, description="Hora (0-23, zona horaria Argentina)")
    minuto: int = Field(0, ge=0, le=59)
    activo: bool = Field(..., description="Si el cron está habilitado")


class CronConfigResponse(BaseModel):
    """Estado de la config del cron."""

    model_config = ConfigDict(from_attributes=True)

    usuario_id: int | None = None
    usuario_nombre: str | None = None
    universidad_id: int | None = None
    hora: int
    minuto: int
    activo: bool


class SnapshotResumenResponse(BaseModel):
    """Resumen de un snapshot generado (respuesta del disparo manual)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    materia_id: int
    generado_en: datetime
    total_alumnos: int
    origen: OrigenSnapshotEnum


class MateriaConfiguradaItem(BaseModel):
    """Materia lista para snapshot, con la fecha de su último snapshot (si tiene)."""

    materia_id: int
    codigo: str
    nombre: str
    ultimo_snapshot: datetime | None = None
    total_alumnos: int | None = None


# ===================== Selectores (árbol cohorte→cuatrimestre→materia) =====================


class MateriaArbol(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str


class CuatrimestreArbol(BaseModel):
    id: int
    numero: int
    nombre: str | None = None
    materias: list[MateriaArbol] = []


class CohorteArbol(BaseModel):
    id: int
    codigo: str
    nombre: str | None = None
    cuatrimestres: list[CuatrimestreArbol] = []


# ===================== Gráfico de torta (avance por estado) =====================


class ConteoEstados(BaseModel):
    """Cantidad de alumnos por estado (las 4 porciones del gráfico)."""

    al_dia: int = 0
    riesgo_medio: int = 0
    riesgo_alto: int = 0
    sin_actividad: int = 0


class AvanceResponse(BaseModel):
    """Datos del gráfico: título dinámico + conteos por estado."""

    titulo: str
    total: int
    generado_en: datetime | None = None
    conteos: ConteoEstados


class AlumnoDetalle(BaseModel):
    """Fila del modal de detalle (alumnos en un estado)."""

    model_config = ConfigDict(from_attributes=True)

    moodle_user_id: int
    nombre: str | None = None
    apellido: str | None = None
    email: str | None = None
    comision: str | None = None
    unidad_alcanzada: int | None = None
    actividad_actual_nombre: str | None = None
    actividad_actual_unidad: int | None = None
    actividad_actual_desaprobada: bool = False
    estado: EstadoAvanceEnum
    # Deudas formateadas (qué le falta) + cómo se nombra la progresión (Unidad/Semana).
    le_falta: str = ""
    etiqueta_unidad: str = "Unidad"
    # Resultados de exámenes formateados (Parcial 1: Aprobó · …). "" si no hay exámenes.
    examenes: str = ""
