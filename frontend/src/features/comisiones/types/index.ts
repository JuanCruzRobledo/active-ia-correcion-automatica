// features/comisiones/types/index.ts
/**
 * TypeScript types for Comisiones feature.
 *
 * Mirrors backend schemas from app/schemas/comision.py
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
 * Ref: docs/specs/06-MODELO-DATOS.md seccion 3.4, 3.5
 */

export interface TutorInfo {
  id: number;
  username: string;
  nombre: string;
  asignado_en: string;
}

export interface MateriaInfo {
  id: number;
  codigo: string;
  nombre: string;
}

export interface Comision {
  id: number;
  materia_id: number;
  nombre: string;
  anio: number;
  activa: boolean;
  moodle_group_id: number | null;
  moodle_group_code: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComisionDetail extends Comision {
  materia: MateriaInfo;
  tutores: TutorInfo[];
}

export interface ComisionListItem {
  id: number;
  materia_id: number;
  materia_nombre: string;
  materia_codigo: string;
  nombre: string;
  anio: number;
  activa: boolean;
  created_at: string;
  num_tutores: number;
  num_entregas: number;
}

export interface ComisionList {
  items: ComisionListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface ComisionCreate {
  materia_id: number;
  nombre: string;
  anio: number;
  tutor_ids?: number[];
  moodle_group_id?: number | null;
  moodle_group_code?: string | null;
}

export interface ComisionUpdate {
  nombre?: string;
  tutor_ids?: number[];
  moodle_group_id?: number | null;
  moodle_group_code?: string | null;
}

export interface TutoresAssign {
  tutor_ids: number[];
}

export interface TutoresResponse {
  comision_id: number;
  tutores: Array<{
    id: number;
    username: string;
    nombre: string;
    rol: string;
    activo: boolean;
    created_at: string;
    last_login: string | null;
  }>;
  message: string;
}

export interface ComisionesFilters {
  materia_id?: number;
  anio?: number;
  include_inactive?: boolean;
  page?: number;
  per_page?: number;
}
