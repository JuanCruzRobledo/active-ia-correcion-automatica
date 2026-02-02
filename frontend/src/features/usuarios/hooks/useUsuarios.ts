// features/usuarios/hooks/useUsuarios.ts
/**
 * React Query hooks for Usuarios feature.
 * 
 * Provides data fetching and mutation hooks with automatic caching and invalidation.
 * Ref: .claude/rules/frontend.md - React Query patterns
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { usuariosService } from '../services/usuarios-service';
import type {
  UsuarioCreate,
  UsuarioUpdate,
  UsuariosFilters,
} from '../types';

/**
 * Query key factory for usuarios
 */
const usuariosKeys = {
  all: ['usuarios'] as const,
  lists: () => [...usuariosKeys.all, 'list'] as const,
  list: (filters?: UsuariosFilters) => [...usuariosKeys.lists(), filters] as const,
  details: () => [...usuariosKeys.all, 'detail'] as const,
  detail: (id: number) => [...usuariosKeys.details(), id] as const,
};

/**
 * Hook to fetch paginated list of usuarios
 */
export const useUsuarios = (filters?: UsuariosFilters) => {
  return useQuery({
    queryKey: usuariosKeys.list(filters),
    queryFn: () => usuariosService.getAll(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch a single usuario by ID
 */
export const useUsuario = (id: number) => {
  return useQuery({
    queryKey: usuariosKeys.detail(id),
    queryFn: () => usuariosService.getById(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to create a new usuario
 */
export const useCreateUsuario = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: UsuarioCreate) => usuariosService.create(data),
    onSuccess: () => {
      // Invalidate all usuario lists to refetch with new data
      queryClient.invalidateQueries({ queryKey: usuariosKeys.lists() });
    },
  });
};

/**
 * Hook to update an existing usuario
 */
export const useUpdateUsuario = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UsuarioUpdate }) =>
      usuariosService.update(id, data),
    onSuccess: (updatedUsuario) => {
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: usuariosKeys.lists() });
      // Update the specific usuario in cache
      queryClient.setQueryData(
        usuariosKeys.detail(updatedUsuario.id),
        updatedUsuario
      );
    },
  });
};

/**
 * Hook to soft delete a usuario
 */
export const useDeleteUsuario = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => usuariosService.delete(id),
    onSuccess: () => {
      // Invalidate all usuario queries to refetch
      queryClient.invalidateQueries({ queryKey: usuariosKeys.all });
    },
  });
};

/**
 * Hook to restore a soft-deleted usuario
 */
export const useRestoreUsuario = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => usuariosService.restore(id),
    onSuccess: (restoredUsuario) => {
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: usuariosKeys.lists() });
      // Update the specific usuario in cache
      queryClient.setQueryData(
        usuariosKeys.detail(restoredUsuario.id),
        restoredUsuario
      );
    },
  });
};

/**
 * Hook to reset a usuario's password
 */
export const useResetPassword = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => usuariosService.resetPassword(id),
    onSuccess: (_, id) => {
      // Invalidate the specific usuario to refetch updated data
      queryClient.invalidateQueries({ queryKey: usuariosKeys.detail(id) });
    },
  });
};

/**
 * Hook to fetch coordinadores (users with COORDINADOR role)
 * Useful for materia assignment forms
 */
export const useCoordinadores = () => {
  return useQuery({
    queryKey: [...usuariosKeys.lists(), { rol: 'COORDINADOR' }],
    queryFn: () => usuariosService.getAll({ rol: 'COORDINADOR', activo: true }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    select: (data) => data.items, // Return only the items array
  });
};

/**
 * Hook to fetch tutores (users with TUTOR role)
 * Useful for comision assignment forms
 */
export const useTutores = () => {
  return useQuery({
    queryKey: [...usuariosKeys.lists(), { rol: 'TUTOR' }],
    queryFn: () => usuariosService.getAll({ rol: 'TUTOR', activo: true }),
    staleTime: 5 * 60 * 1000, // 5 minutes
    select: (data) => data.items, // Return only the items array
  });
};
