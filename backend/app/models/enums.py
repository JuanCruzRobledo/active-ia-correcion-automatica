# app/models/enums.py
"""
Enumerations for Active-IA models.

Ref: docs/specs/06-MODELO-DATOS.md seccion 3
"""

from enum import Enum


class RolEnum(str, Enum):
    """Roles de usuario en el sistema."""

    ADMIN = "ADMIN"
    COORDINADOR = "COORDINADOR"
    TUTOR = "TUTOR"
    GESTOR = "GESTOR"  # Gestión/reportes de usuarios de Moodle (pantalla "Gestión")


class TipoRubricaEnum(str, Enum):
    """Tipos de rúbrica de evaluación."""

    TP = "TP"
    PARCIAL_1 = "PARCIAL_1"
    PARCIAL_2 = "PARCIAL_2"
    RECUPERATORIO_1 = "RECUPERATORIO_1"
    RECUPERATORIO_2 = "RECUPERATORIO_2"
    FINAL = "FINAL"
    GLOBAL = "GLOBAL"


class EstadoEntregaEnum(str, Enum):
    """Estados posibles de una entrega."""

    SUBIDA = "SUBIDA"  # Archivo cargado, sin corregir
    PENDIENTE = "PENDIENTE"  # En proceso de corrección
    CORREGIDA = "CORREGIDA"  # Corrección completada
    ERROR = "ERROR"  # Falló el proceso


class FuenteRubricaEnum(str, Enum):
    """Fuente de creación de la rúbrica."""

    MANUAL = "manual"
    PDF = "pdf"


class EstadoCriterioEnum(str, Enum):
    """Estados de evaluación de un criterio."""

    OK = "OK"  # Criterio cumplido satisfactoriamente
    WARNING = "WARNING"  # Criterio con observaciones menores
    ERROR = "ERROR"  # Criterio con problemas significativos


class TipoActividadEnum(str, Enum):
    """Tipos de actividad que se registran en el sistema para auditoría."""

    USUARIO_CREADO = "USUARIO_CREADO"
    MATERIA_CREADA = "MATERIA_CREADA"
    COMISION_CREADA = "COMISION_CREADA"
    RUBRICA_CREADA = "RUBRICA_CREADA"


class MoodleSyncEstado(str, Enum):
    """Estado de la sincronización de una corrección hacia Moodle."""

    PENDIENTE = "PENDIENTE"  # Aún no enviada
    ENVIADO = "ENVIADO"  # Nota + feedback publicados en Moodle
    ERROR = "ERROR"  # Falló el envío


class EstadoAvanceEnum(str, Enum):
    """Estado de avance de un alumno respecto a la unidad actual de la materia.

    Se calcula en el snapshot del Dashboard de Gestores comparando la unidad
    más alta completada por el alumno (unidad_alcanzada) contra materia.unidad_actual.
    Ver PLAN_DASHBOARD_GESTORES.md §4.
    """

    AL_DIA = "AL_DIA"  # delta <= 0 (verde): alcanzó/superó la unidad actual
    RIESGO_MEDIO = "RIESGO_MEDIO"  # delta == 1 (naranja): una unidad atrás
    RIESGO_ALTO = "RIESGO_ALTO"  # delta >= 2 (rojo): dos o más unidades atrás
    SIN_ACTIVIDAD = "SIN_ACTIVIDAD"  # (gris): sin ninguna actividad completada


class OrigenSnapshotEnum(str, Enum):
    """Origen de un snapshot de avance."""

    CRON = "CRON"  # Generado por el job diario
    MANUAL = "MANUAL"  # Disparado a mano (botón de pruebas)


class TipoNotificacionEnum(str, Enum):
    """Destinatario de una notificación de avance por email.

    Ver PLAN_NOTIFICACIONES_EMAIL.md §1.
    """

    ALUMNO = "ALUMNO"  # tabla HTML en el cuerpo con sus materias/actividades faltantes
    TUTOR_ACADEMICO = "TUTOR_ACADEMICO"  # PDF adjunto, por sus comisiones
    TUTOR_NEXO = "TUTOR_NEXO"  # Excel adjunto, por su regional


class EstadoEnvioEnum(str, Enum):
    """Estado de un email en la cola de envío (EnvioEmailLog)."""

    PENDIENTE = "PENDIENTE"  # encolado, aún no enviado
    ENVIADO = "ENVIADO"  # aceptado por Resend (con resend_id)
    ERROR = "ERROR"  # falló tras reintentos
    OMITIDO = "OMITIDO"  # sin destinatario válido / sin nada que informar


class TipoComponenteEnum(str, Enum):
    """Tipo de un componente evaluable de una unidad.

    Es SOLO una etiqueta para el reporte ("Te falta el Quiz de la Unidad 3"); la
    LÓGICA de "realizado/deuda" la decide la FUENTE, no el tipo. Ver §9.bis F.
    """

    TP = "TP"  # trabajo práctico / entregable
    QUIZ = "QUIZ"  # cuestionario
    AUTOEVALUACION = "AUTOEVALUACION"  # autoevaluación
    CIERRE = "CIERRE"  # actividad de cierre


class FuenteComponenteEnum(str, Enum):
    """Fuente de verdad para saber si un componente está realizado. §9.bis F.

    - SEGUIMIENTO: por el completion de Moodle (state ∈ {1,2,3} = hecho).
      OJO: requiere que la actividad tenga activado el seguimiento de finalización.
    - CALIFICACION: por la nota (Aprobado/Desaprobado o nota numérica cargada).
    """

    SEGUIMIENTO = "SEGUIMIENTO"
    CALIFICACION = "CALIFICACION"
