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
    TPI = "TPI"  # Trabajo Práctico Integrador
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
    # Acciones manuales de las funciones nuevas (Dashboard de Gestores / Notificaciones).
    COHORTE_CREADA = "COHORTE_CREADA"
    TUTOR_NEXO_CREADO = "TUTOR_NEXO_CREADO"
    EXAMEN_CREADO = "EXAMEN_CREADO"
    # Integración con clientes externos (change api-escritura-trabajos-practicos).
    # En un upsert idempotente la auditoría es la ÚNICA forma de reconstruir qué
    # publicación dejó al TP como está: el estado final no lo dice.
    TRABAJO_PRACTICO_PUBLICADO = "TRABAJO_PRACTICO_PUBLICADO"
    SNAPSHOT_GENERADO = "SNAPSHOT_GENERADO"
    NOTIFICACIONES_ENVIADAS = "NOTIFICACIONES_ENVIADAS"
    CIERRE_CURSADA_GENERADO = "CIERRE_CURSADA_GENERADO"
    # Soft delete: hoy es el unico dominio del sistema que audita BORRADOS.
    ENTREGA_ELIMINADA = "ENTREGA_ELIMINADA"
    ENTREGA_RESTAURADA = "ENTREGA_RESTAURADA"
    CORRECCION_RECORREGIDA = "CORRECCION_RECORREGIDA"


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


class TipoExamenEnum(str, Enum):
    """Tipo de examen de una materia (seguimiento de evaluaciones sumativas).

    A diferencia de los componentes de unidad (que miden AVANCE de contenido), los
    exámenes son evaluaciones de aprobación. RECUPERATORIO/EXTENSION/EXTRAORDINARIA
    se vinculan a un PARCIAL (rescatan su nota). GLOBAL va suelto.
    """

    PARCIAL = "PARCIAL"
    RECUPERATORIO = "RECUPERATORIO"
    EXTENSION = "EXTENSION"
    EXTRAORDINARIA = "EXTRAORDINARIA"
    GLOBAL = "GLOBAL"


class TipoActividadMoodleEnum(str, Enum):
    """Tipo de actividad de Moodle subyacente a un examen de la materia.

    Distingue si el examen es una Tarea (`assign`) o un Cuestionario (`quiz`).
    Los valores van en minúscula para comparar directo con el `modname` que
    devuelve Moodle. `assign` es el default (comportamiento histórico): resuelve
    el link a `/mod/assign/view.php` y usa el grade estructural
    (`mod_assign_get_grades`); `quiz` resuelve a `/mod/quiz/view.php` y toma la
    nota del calificador por texto.
    """

    ASSIGN = "assign"
    QUIZ = "quiz"


class ModoAprobacionEnum(str, Enum):
    """Cómo se interpreta la nota de un examen para decidir aprobado/desaprobado.

    - ESCALA: escala de texto de Moodle ("Aprobado"/"Desaprobado"). Vacío = ausente.
    - NUMERICO: nota numérica; aprueba si nota >= nota_minima. Vacío = ausente.
    """

    ESCALA = "ESCALA"
    NUMERICO = "NUMERICO"


class CategoriaItemCierreEnum(str, Enum):
    """Categoría de un ítem del calificador de Moodle para el cierre de cursada.

    Mapeo confirmado por el coordinador (ver CierreCursadaItem) — nunca se usa
    una sugerencia sin confirmar para calcular. Ver cierre_cursada_calculo.py.
    """

    TP = "TP"
    AUTOEVAL = "AUTOEVAL"
    PARCIAL_1 = "PARCIAL_1"
    PARCIAL_2 = "PARCIAL_2"
    TPI = "TPI"
    IGNORAR = "IGNORAR"


class EstadoCierreEnum(str, Enum):
    """Veredicto de cierre de cursada de un alumno en una materia.

    ABANDONO se distingue de RECURSA: un alumno ABANDONO no rindió ningún
    examen ni el global (todo en `N/E`); RECURSA sí rindió algo pero no
    alcanzó promoción ni regularización. Ver `calcular_estado_cierre`.
    """

    PROMOCIONA = "PROMOCIONA"
    REGULARIZA = "REGULARIZA"
    RECURSA = "RECURSA"
    ABANDONO = "ABANDONO"
