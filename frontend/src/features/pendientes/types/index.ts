export interface ComisionPendiente {
  id: number;
  nombre: string;
  codigo: string;
  groupId: number | null;
  espera: number;
  corregidos: number;
  sinEntrega: number;
  moodleGraderUrl: string | null;
}

export interface UnidadPendiente {
  id: number;
  titulo: string;
  subtitulo: string;
  cmid: number | null;
  espera: number;
  corregidos: number;
  sinEntrega: number;
  comisiones: ComisionPendiente[];
}

export interface MateriaPendiente {
  id: number;
  nombre: string;
  totalEspera: number;
  totalCorregidos: number;
  totalSinEntrega: number;
  unidades: UnidadPendiente[];
}

export interface MateriasPendientesResponse {
  materias: MateriaPendiente[];
}

// ── Importación desde Moodle ──────────────────────────────────────────────

export type ImportScope = 'comision_unidad' | 'materia' | 'tutor';

export interface ImportarMoodleRequest {
  scope: ImportScope;
  rubrica_id?: number;
  comision_id?: number;
  materia_id?: number;
}

export interface ImportErrorItem {
  alumno: string;
  motivo: string;
}

export interface ImportDetalleRubrica {
  rubrica_id: number;
  titulo: string;
  comision_id: number;
  cargadas: number;
}

export interface ImportarMoodleResponse {
  cargadas: number;
  duplicadas: number;
  omitidas_ya_corregidas: number;
  reentregas: number;
  sin_archivos: number;
  errores: ImportErrorItem[];
  detalle_por_rubrica: ImportDetalleRubrica[];
}
