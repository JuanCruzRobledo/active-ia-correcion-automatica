// Tipos del dashboard de gestores (lectura)

export type EstadoAvance = 'AL_DIA' | 'RIESGO_MEDIO' | 'RIESGO_ALTO' | 'SIN_ACTIVIDAD';

export interface MateriaArbol {
  id: number;
  codigo: string;
  nombre: string;
}

export interface CuatrimestreArbol {
  id: number;
  numero: number;
  nombre?: string | null;
  materias: MateriaArbol[];
}

export interface CohorteArbol {
  id: number;
  codigo: string;
  nombre?: string | null;
  cuatrimestres: CuatrimestreArbol[];
}

export interface ConteoEstados {
  al_dia: number;
  riesgo_medio: number;
  riesgo_alto: number;
  sin_actividad: number;
}

export interface AvanceResponse {
  titulo: string;
  total: number;
  generado_en: string | null;
  conteos: ConteoEstados;
}

export interface AlumnoDetalle {
  moodle_user_id: number;
  nombre?: string | null;
  apellido?: string | null;
  email?: string | null;
  comision?: string | null;
  unidad_alcanzada?: number | null;
  actividad_actual_nombre?: string | null;
  actividad_actual_unidad?: number | null;
  actividad_actual_desaprobada: boolean;
  estado: EstadoAvance;
  /** Deudas formateadas (qué le falta) y cómo se nombra la progresión (Unidad/Semana). */
  le_falta: string;
  etiqueta_unidad: string;
  /** Resultados de exámenes formateados (Parcial 1: Aprobó · …). "" si no hay. */
  examenes: string;
}
