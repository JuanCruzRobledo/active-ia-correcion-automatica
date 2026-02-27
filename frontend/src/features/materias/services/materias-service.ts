// Materias service for API calls
import { apiClient } from '@/shared/services/api-client';
import type {
  MateriaList,
  MateriaDetail,
  MateriaCreate,
  MateriaUpdate,
  MateriasFilters,
  CoordinadoresAssign,
  CoordinadoresResponse,
} from '../types';

export const materiasService = {
  /**
   * Get paginated list of materias with optional filters
   */
  getAll: async (filters?: MateriasFilters): Promise<MateriaList> => {
    const params = new URLSearchParams();

    // Si activa es undefined ("Todas") o false ("Inactivas"), hay que pedir
    // include_inactive=true para que el backend devuelva registros con activa=False
    if (filters?.activa === undefined || filters?.activa === false) {
      params.append('include_inactive', 'true');
    }

    if (filters?.activa !== undefined) {
      params.append('activa', filters.activa.toString());
    }
    if (filters?.search) {
      params.append('search', filters.search);
    }
    if (filters?.page) {
      params.append('page', filters.page.toString());
    }
    if (filters?.per_page) {
      params.append('per_page', filters.per_page.toString());
    }

    const { data } = await apiClient.get<MateriaList>(
      `/materias?${params.toString()}`
    );
    return data;
  },

  /**
   * Get single materia by ID with coordinators
   */
  getById: async (id: number): Promise<MateriaDetail> => {
    const { data } = await apiClient.get<MateriaDetail>(`/materias/${id}`);
    return data;
  },

  /**
   * Create new materia
   */
  create: async (materia: MateriaCreate): Promise<MateriaDetail> => {
    const { data } = await apiClient.post<MateriaDetail>('/materias', materia);
    return data;
  },

  /**
   * Update existing materia
   */
  update: async (id: number, materia: MateriaUpdate): Promise<MateriaDetail> => {
    const { data } = await apiClient.put<MateriaDetail>(`/materias/${id}`, materia);
    return data;
  },

  /**
   * Soft delete materia
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/materias/${id}`);
  },

  /**
   * Restore soft-deleted materia
   */
  restore: async (id: number): Promise<MateriaDetail> => {
    const { data } = await apiClient.post<MateriaDetail>(`/materias/${id}/restore`);
    return data;
  },

  /**
   * Assign coordinators to materia
   */
  assignCoordinadores: async (
    id: number,
    coordinadores: CoordinadoresAssign
  ): Promise<CoordinadoresResponse> => {
    const { data } = await apiClient.post<CoordinadoresResponse>(
      `/materias/${id}/coordinadores`,
      coordinadores
    );
    return data;
  },
};
