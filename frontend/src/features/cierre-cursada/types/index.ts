export type EstadoCierre = 'PROMOCIONA' | 'REGULARIZA' | 'RECURSA';

export interface GenerarCierreInput {
  cuatrimestre_id: number;
}

export interface CierreRun {
  id: number;
  materia_id: number;
  cuatrimestre_id: number;
  generado_por_id: number;
  total_alumnos: number;
  total_promociona: number;
  total_regulariza: number;
  total_recursa: number;
  created_at: string;
}
