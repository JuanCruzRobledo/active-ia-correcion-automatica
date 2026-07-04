export type CategoriaItemCierre =
  | 'TP'
  | 'AUTOEVAL'
  | 'PARCIAL_1'
  | 'PARCIAL_2'
  | 'TPI'
  | 'IGNORAR';

export type EstadoCierre = 'PROMOCIONA' | 'REGULARIZA' | 'RECURSA';

export interface CierreItemSugerido {
  moodle_cmid: number;
  nombre_moodle: string;
  orden: number | null;
  categoria: CategoriaItemCierre;
  unidad: number | null;
  opcional: boolean;
  confirmado: boolean;
}

export interface CierreItemConfirmado {
  moodle_cmid: number;
  nombre_moodle: string;
  categoria: CategoriaItemCierre;
  unidad?: number | null;
  opcional?: boolean;
  orden?: number | null;
}

export interface ReglasCierreOverride {
  autoeval_min_pct?: number;
  parcial_promocion_min_pct?: number;
  parcial_regulariza_min_pct?: number;
  tpi_min_pct?: number;
}

export interface GenerarCierreInput {
  cuatrimestre_id: number;
  umbral_tp_pct: number;
  reglas?: ReglasCierreOverride;
}

export interface CierreRun {
  id: number;
  materia_id: number;
  cuatrimestre_id: number;
  umbral_tp_pct: number;
  generado_por_id: number;
  total_alumnos: number;
  total_promociona: number;
  total_regulariza: number;
  total_recursa: number;
  created_at: string;
}
