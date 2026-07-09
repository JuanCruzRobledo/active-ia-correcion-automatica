// Tipos de la config de dashboard por materia (unidades + vinculación)

// §9.bis F — componentes evaluables dinámicos por unidad.
export type TipoComponente = 'TP' | 'QUIZ' | 'AUTOEVALUACION' | 'CIERRE';
export type FuenteComponente = 'SEGUIMIENTO' | 'CALIFICACION';

export interface ComponenteUnidad {
  id: number;
  tipo: TipoComponente;
  moodle_cmid: number;
  fuente: FuenteComponente;
  /** Cómo se interpreta la nota si fuente=CALIFICACION: ESCALA o NUMERICO. */
  modo_aprobacion: ModoAprobacion;
  /** Nota mínima para aprobar si modo_aprobacion=NUMERICO (escala de Moodle). */
  nota_minima: number | null;
  orden: number;
}

export interface Unidad {
  id: number;
  materia_id: number;
  numero: number;
  moodle_section_id: number;
  nombre?: string | null;
  componentes: ComponenteUnidad[];
}

export interface MoodleActividad {
  cmid: number;
  nombre: string;
  modname: string;
  // false => sin seguimiento de finalización (conviene medirla por CALIFICACIÓN).
  tiene_seguimiento: boolean;
}

// Un componente a guardar (sin id; el orden lo da la posición en la lista).
export interface ComponenteInput {
  tipo: TipoComponente;
  moodle_cmid: number;
  fuente: FuenteComponente;
  modo_aprobacion: ModoAprobacion;
  nota_minima: number | null;
}

export interface UnidadComponentes {
  componentes: ComponenteInput[];
}

export interface UnidadCreate {
  numero: number;
  moodle_section_id: number;
  nombre?: string | null;
}

export interface MateriaDashboardConfig {
  cuatrimestre_id: number | null;
  unidad_actual: number | null;
  moodle_section_fin_id: number | null;
  /** Cómo se llama la progresión en los reportes: 'Unidad' (default) o 'Semana'. */
  etiqueta_unidad: string;
  /** Atraso (en unidades/semanas) desde el cual el alumno entra en riesgo medio. */
  riesgo_medio_desde: number;
  /** Atraso desde el cual entra en riesgo alto (debe ser > riesgo_medio_desde). */
  riesgo_alto_desde: number;
}

export interface MateriaDashboardConfigResponse extends MateriaDashboardConfig {
  materia_id: number;
}

export interface MoodleSeccionItem {
  moodle_section_id: number;
  section: number;
  nombre: string;
  es_cabecera_sugerida: boolean;
  numero_sugerido: number | null;
}

export interface MoodleSeccionesSugeridas {
  materia_id: number;
  moodle_course_id: number;
  secciones: MoodleSeccionItem[];
  cabeceras_sugeridas: UnidadCreate[];
}

// ===================== Exámenes de la materia =====================

export type TipoExamen =
  | 'PARCIAL'
  | 'RECUPERATORIO'
  | 'EXTENSION'
  | 'EXTRAORDINARIA'
  | 'GLOBAL';
export type ModoAprobacion = 'ESCALA' | 'NUMERICO';

/** Actividad de Moodle subyacente de un examen: Tarea (assign) o Cuestionario (quiz). */
export type TipoActividadMoodle = 'assign' | 'quiz';

/** Tipos cuyo resultado se rescata vinculándose a un PARCIAL o GLOBAL. */
export const TIPOS_RESCATE: TipoExamen[] = [
  'RECUPERATORIO',
  'EXTENSION',
  'EXTRAORDINARIA',
];

export interface ExamenMateria {
  id: number;
  materia_id: number;
  tipo: TipoExamen;
  /** Número derivado por tipo (Parcial 1, 2…). */
  numero: number;
  /** Etiqueta visible, ej. 'Parcial 2'. */
  etiqueta: string;
  moodle_cmid: number;
  /** Actividad de Moodle: 'assign' (Tarea) o 'quiz' (Cuestionario). */
  tipo_actividad: TipoActividadMoodle;
  modo_aprobacion: ModoAprobacion;
  nota_minima: number | null;
  recupera_examen_id: number | null;
  orden: number;
}

/** Alta/edición de un examen (la numeración la asigna el backend). */
export interface ExamenInput {
  tipo: TipoExamen;
  moodle_cmid: number;
  tipo_actividad: TipoActividadMoodle;
  modo_aprobacion: ModoAprobacion;
  nota_minima: number | null;
  recupera_examen_id: number | null;
}
