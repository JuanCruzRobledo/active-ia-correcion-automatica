// features/rubricas/services/rubricas-service.ts
/**
 * API service for Rubricas feature.
 *
 * Handles all HTTP requests to rubricas endpoints.
 * Ref: backend/app/routers/rubricas.py
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  Rubrica,
  RubricaDetail,
  RubricaList,
  RubricaCreate,
  RubricaUpdate,
  RubricaDuplicar,
  RubricasFilters,
} from '../types';

/**
 * Rubricas service with all API operations
 */
export const rubricasService = {
  /**
   * Get paginated list of rubricas with optional filters
   */
  getAll: async (filters?: RubricasFilters): Promise<RubricaList> => {
    const params = new URLSearchParams();

    if (filters?.materia_id) params.append('materia_id', String(filters.materia_id));
    if (filters?.tipo) params.append('tipo', filters.tipo);
    if (filters?.anio) params.append('anio', String(filters.anio));
    if (filters?.include_inactive !== undefined) {
      params.append('include_inactive', String(filters.include_inactive));
    }
    if (filters?.page) params.append('page', String(filters.page));
    if (filters?.per_page) params.append('per_page', String(filters.per_page));

    const response = await apiClient.get<RubricaList>(
      `/rubricas?${params.toString()}`
    );
    return response.data;
  },

  /**
   * Get single rubrica by ID with full details
   */
  getById: async (id: number): Promise<RubricaDetail> => {
    const response = await apiClient.get<RubricaDetail>(`/rubricas/${id}`);
    return response.data;
  },

  /**
   * Create new rubrica
   */
  create: async (data: RubricaCreate): Promise<Rubrica> => {
    const response = await apiClient.post<Rubrica>('/rubricas', data);
    return response.data;
  },

  /**
   * Update existing rubrica
   */
  update: async (id: number, data: RubricaUpdate): Promise<Rubrica> => {
    const response = await apiClient.put<Rubrica>(`/rubricas/${id}`, data);
    return response.data;
  },

  /**
   * Soft delete rubrica
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/rubricas/${id}`);
  },

  /**
   * Restore soft-deleted rubrica
   */
  restore: async (id: number): Promise<Rubrica> => {
    const response = await apiClient.post<Rubrica>(`/rubricas/${id}/restore`);
    return response.data;
  },

  /**
   * Duplicate rubrica to a new year
   */
  duplicar: async (id: number, data: RubricaDuplicar): Promise<Rubrica> => {
    const response = await apiClient.post<Rubrica>(
      `/rubricas/${id}/duplicar`,
      data
    );
    return response.data;
  },

  /**
   * Generate rubrica from PDF using AI
   * Note: This endpoint uses multipart/form-data
   * Returns suggested rubrica structure (not a saved rubrica yet)
   */
  generarDesdePDF: async (
    tipo: string,
    file: File
  ): Promise<any> => {
    const formData = new FormData();
    // Backend expects 'pdf_file' and 'tipo_rubrica'
    formData.append('pdf_file', file);
    formData.append('tipo_rubrica', tipo);

    const response = await apiClient.post<any>(
      '/rubricas/desde-pdf',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  },
};
