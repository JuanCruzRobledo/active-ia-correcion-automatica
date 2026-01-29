// features/comisiones/services/comisiones-service.ts
/**
 * Service layer for Comisiones API calls.
 *
 * Handles all HTTP requests to the comisiones endpoints.
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 5
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  Comision,
  ComisionDetail,
  ComisionList,
  ComisionCreate,
  ComisionUpdate,
  TutoresAssign,
  TutoresResponse,
  ComisionesFilters,
} from '../types';

export const comisionesService = {
  /**
   * Get paginated list of comisiones with optional filters
   */
  getAll: async (filters?: ComisionesFilters): Promise<ComisionList> => {
    const params = new URLSearchParams();

    if (filters?.materia_id) {
      params.append('materia_id', String(filters.materia_id));
    }

    if (filters?.anio) {
      params.append('anio', String(filters.anio));
    }

    if (filters?.include_inactive !== undefined) {
      params.append('include_inactive', String(filters.include_inactive));
    }

    if (filters?.page) {
      params.append('page', String(filters.page));
    }

    if (filters?.per_page) {
      params.append('per_page', String(filters.per_page));
    }

    const queryString = params.toString();
    const url = `/comisiones${queryString ? `?${queryString}` : ''}`;

    const { data } = await apiClient.get<ComisionList>(url);
    return data;
  },

  /**
   * Get a single comision by ID with full details (including materia and tutores)
   */
  getById: async (id: number): Promise<ComisionDetail> => {
    const { data } = await apiClient.get<ComisionDetail>(`/comisiones/${id}`);
    return data;
  },

  /**
   * Create a new comision
   */
  create: async (comision: ComisionCreate): Promise<Comision> => {
    const { data } = await apiClient.post<Comision>('/comisiones', comision);
    return data;
  },

  /**
   * Update an existing comision
   */
  update: async (id: number, comision: ComisionUpdate): Promise<Comision> => {
    const { data } = await apiClient.put<Comision>(`/comisiones/${id}`, comision);
    return data;
  },

  /**
   * Soft delete a comision (mark as inactive)
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/comisiones/${id}`);
  },

  /**
   * Restore a soft-deleted comision
   */
  restore: async (id: number): Promise<Comision> => {
    const { data } = await apiClient.post<Comision>(`/comisiones/${id}/restore`);
    return data;
  },

  /**
   * Assign tutors to a comision
   * Replaces all existing tutor assignments with the new list
   */
  assignTutores: async (
    id: number,
    tutores: TutoresAssign
  ): Promise<TutoresResponse> => {
    const { data } = await apiClient.post<TutoresResponse>(
      `/comisiones/${id}/tutores`,
      tutores
    );
    return data;
  },
};
