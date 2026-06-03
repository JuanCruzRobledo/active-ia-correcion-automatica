// Tipos de la config de dashboard por materia (unidades + vinculación)

export interface Unidad {
  id: number;
  materia_id: number;
  numero: number;
  moodle_section_id: number;
  nombre?: string | null;
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
