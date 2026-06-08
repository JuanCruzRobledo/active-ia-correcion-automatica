// Tipos de la config de dashboard por materia (unidades + vinculación)

// §9.bis F — componentes evaluables dinámicos por unidad.
export type TipoComponente = 'TP' | 'QUIZ' | 'AUTOEVALUACION' | 'CIERRE';
export type FuenteComponente = 'SEGUIMIENTO' | 'CALIFICACION';

export interface ComponenteUnidad {
  id: number;
  tipo: TipoComponente;
  moodle_cmid: number;
  fuente: FuenteComponente;
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
