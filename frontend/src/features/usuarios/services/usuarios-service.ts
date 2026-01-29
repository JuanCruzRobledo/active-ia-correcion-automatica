// features/usuarios/services/usuarios-service.ts
/**
 * Service layer for Usuarios API calls.
 * 
 * Handles all HTTP requests to the usuarios endpoints.
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 3
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  Usuario,
  UsuarioList,
  UsuarioCreate,
  UsuarioUpdate,
  UsuarioCreateResponse,
  ResetPasswordResponse,
  UsuariosFilters,
} from '../types';

export const usuariosService = {
  /**
   * Get paginated list of users with optional filters
   */
  getAll: async (filters?: UsuariosFilters): Promise<UsuarioList> => {
    const params = new URLSearchParams();
    
    if (filters?.rol && filters.rol !== 'TODOS') {
      params.append('rol', filters.rol);
    }
    
    if (filters?.activo !== undefined && filters.activo !== 'TODOS') {
      params.append('activo', String(filters.activo));
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

    const queryString = params.toString();
    const url = `/usuarios${queryString ? `?${queryString}` : ''}`;
    
    const { data } = await apiClient.get<UsuarioList>(url);
    return data;
  },

  /**
   * Get a single user by ID
   */
  getById: async (id: number): Promise<Usuario> => {
    const { data } = await apiClient.get<Usuario>(`/usuarios/${id}`);
    return data;
  },

  /**
   * Create a new user
   * Returns the created user and a temporary password
   */
  create: async (usuario: UsuarioCreate): Promise<UsuarioCreateResponse> => {
    const { data } = await apiClient.post<UsuarioCreateResponse>('/usuarios', usuario);
    return data;
  },

  /**
   * Update an existing user
   */
  update: async (id: number, usuario: UsuarioUpdate): Promise<Usuario> => {
    const { data } = await apiClient.put<Usuario>(`/usuarios/${id}`, usuario);
    return data;
  },

  /**
   * Soft delete a user (mark as inactive)
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/usuarios/${id}`);
  },

  /**
   * Restore a soft-deleted user
   */
  restore: async (id: number): Promise<Usuario> => {
    const { data } = await apiClient.post<Usuario>(`/usuarios/${id}/restore`);
    return data;
  },

  /**
   * Reset user's password
   * Returns a new temporary password
   */
  resetPassword: async (id: number): Promise<ResetPasswordResponse> => {
    const { data } = await apiClient.post<ResetPasswordResponse>(
      `/usuarios/${id}/reset-password`
    );
    return data;
  },
};
