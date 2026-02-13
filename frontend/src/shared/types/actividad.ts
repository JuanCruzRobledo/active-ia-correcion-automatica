/**
 * Types for Actividad (Activity/Audit) domain
 *
 * Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
 */

/**
 * Tipos de actividad en el sistema.
 * Mirrors: backend/app/models/enums.py::TipoActividadEnum
 */
export type TipoActividad =
  | 'USUARIO_CREADO'
  | 'MATERIA_CREADA'
  | 'COMISION_CREADA'
  | 'RUBRICA_CREADA';

/**
 * TipoActividad values object for runtime usage.
 */
export const TIPO_ACTIVIDAD = {
  USUARIO_CREADO: 'USUARIO_CREADO' as const,
  MATERIA_CREADA: 'MATERIA_CREADA' as const,
  COMISION_CREADA: 'COMISION_CREADA' as const,
  RUBRICA_CREADA: 'RUBRICA_CREADA' as const,
} as const;

export interface Actividad {
  id: number;
  tipo: TipoActividad;
  descripcion: string;
  entidad_id: number;
  entidad_nombre: string;
  usuario_id: number | null;
  created_at: string;
  usuario_nombre: string | null;
  usuario_rol: string | null;
}

export interface ActividadListResponse {
  items: Actividad[];
  total: number;
}
