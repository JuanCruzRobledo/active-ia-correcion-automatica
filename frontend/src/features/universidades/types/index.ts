// features/universidades/types/index.ts
/**
 * Types for the universidades feature (Fase 5 multi-tenant).
 *
 * Ref: backend/app/schemas/universidad.py
 */
import type { Rol } from '@/shared/types';

/**
 * Una universidad del selector propio del usuario autenticado.
 * Mirrors: backend/app/schemas/universidad.py::UniversidadPropia
 */
export interface UniversidadPropia {
  id: number;
  nombre: string;
  rol: Rol;
}

/**
 * Universidad completa (ABM).
 * Mirrors: backend/app/schemas/universidad.py::UniversidadResponse
 */
export interface Universidad {
  id: number;
  nombre: string;
  moodle_host: string | null;
  activa: boolean;
  created_at: string;
  updated_at: string;
}

/**
 * Item reducido del listado paginado (ABM).
 * Mirrors: backend/app/schemas/universidad.py::UniversidadListItem
 */
export interface UniversidadListItem {
  id: number;
  nombre: string;
  moodle_host: string | null;
  activa: boolean;
}

/**
 * Listado paginado de universidades (ABM).
 * Mirrors: backend/app/schemas/universidad.py::UniversidadList
 */
export interface UniversidadList {
  items: UniversidadListItem[];
  total: number;
  page: number;
  per_page: number;
}

/** Mirrors: backend/app/schemas/universidad.py::UniversidadCreate */
export interface UniversidadCreate {
  nombre: string;
  moodle_host?: string | null;
}

/** Mirrors: backend/app/schemas/universidad.py::UniversidadUpdate */
export interface UniversidadUpdate {
  nombre?: string;
  moodle_host?: string | null;
  activa?: boolean;
}

/** Filtros del listado del ABM. */
export interface UniversidadesFilters {
  includeInactive?: boolean;
  search?: string;
  page?: number;
  per_page?: number;
}
