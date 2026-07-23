// features/universidades/services/universidades-service.ts
/**
 * Service layer for Universidades API calls (Fase 5 multi-tenant).
 *
 * `getMias()` alimenta el selector de universidad (D5); el resto es el ABM
 * de superadmin.
 *
 * Ref: backend/app/routers/universidades.py
 */
import { apiClient } from '@/shared/services/api-client';
import type {
  Universidad,
  UniversidadCreate,
  UniversidadList,
  UniversidadPropia,
  UniversidadUpdate,
  UniversidadesFilters,
} from '../types';

export const universidadesService = {
  /** Universidades del usuario autenticado (para el selector). */
  getMias: async (): Promise<UniversidadPropia[]> => {
    const { data } = await apiClient.get<UniversidadPropia[]>('/universidades/mias');
    return data;
  },

  /** Listado paginado (ABM, superadmin). */
  getAll: async (filters?: UniversidadesFilters): Promise<UniversidadList> => {
    const params = new URLSearchParams();
    if (filters?.includeInactive !== undefined) {
      params.append('include_inactive', String(filters.includeInactive));
    }
    if (filters?.search) {
      params.append('search', filters.search);
    }
    if (filters?.page) {
      params.append('page', String(filters.page));
    }
    if (filters?.per_page) {
      params.append('per_page', String(filters.per_page));
    }
    const query = params.toString();
    const { data } = await apiClient.get<UniversidadList>(
      `/universidades${query ? `?${query}` : ''}`
    );
    return data;
  },

  /** Alta de universidad (ABM, superadmin). */
  create: async (payload: UniversidadCreate): Promise<Universidad> => {
    const { data } = await apiClient.post<Universidad>('/universidades', payload);
    return data;
  },

  /** Edición de universidad (ABM, superadmin). */
  update: async (id: number, payload: UniversidadUpdate): Promise<Universidad> => {
    const { data } = await apiClient.put<Universidad>(`/universidades/${id}`, payload);
    return data;
  },

  /** Baja lógica (ABM, superadmin). */
  remove: async (id: number): Promise<void> => {
    await apiClient.delete(`/universidades/${id}`);
  },
};
