// features/comisiones/hooks/useComisiones.ts
/**
 * React Query hooks for Comisiones feature.
 *
 * Provides data fetching and mutation hooks with automatic caching and invalidation.
 * Ref: .claude/rules/frontend.md - React Query patterns
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { comisionesService } from '../services/comisiones-service';
import type {
  ComisionCreate,
  ComisionUpdate,
  TutoresAssign,
  ComisionesFilters,
} from '../types';

/**
 * Query key factory for comisiones
 */
const comisionesKeys = {
  all: ['comisiones'] as const,
  lists: () => [...comisionesKeys.all, 'list'] as const,
  list: (filters?: ComisionesFilters) => [...comisionesKeys.lists(), filters] as const,
  details: () => [...comisionesKeys.all, 'detail'] as const,
  detail: (id: number) => [...comisionesKeys.details(), id] as const,
};

/**
 * Hook to fetch paginated list of comisiones
 */
export const useComisiones = (filters?: ComisionesFilters) => {
  return useQuery({
    queryKey: comisionesKeys.list(filters),
    queryFn: () => comisionesService.getAll(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch a single comision by ID with full details
 */
export const useComision = (id: number) => {
  return useQuery({
    queryKey: comisionesKeys.detail(id),
    queryFn: () => comisionesService.getById(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to create a new comision
 */
export const useCreateComision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: ComisionCreate) => comisionesService.create(data),
    onSuccess: () => {
      // Invalidate all comision lists to refetch with new data
      queryClient.invalidateQueries({ queryKey: comisionesKeys.lists() });
    },
  });
};

/**
 * Hook to update an existing comision
 */
export const useUpdateComision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ComisionUpdate }) =>
      comisionesService.update(id, data),
    onSuccess: (_data, variables) => {
    // refresca todas las listas
    queryClient.invalidateQueries({
      queryKey: comisionesKeys.lists(),
    });

    // refresca el detail REAL (con tutores)
    queryClient.invalidateQueries({
      queryKey: comisionesKeys.detail(variables.id),
    });
  },

  });
};

/**
 * Hook to soft delete a comision
 */
export const useDeleteComision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => comisionesService.delete(id),
    onSuccess: () => {
      // Invalidate all comision queries to refetch
      queryClient.invalidateQueries({ queryKey: comisionesKeys.all });
    },
  });
};

/**
 * Hook to restore a soft-deleted comision
 */
export const useRestoreComision = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => comisionesService.restore(id),
    onSuccess: (restoredComision) => {
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: comisionesKeys.lists() });
      // Update the specific comision in cache
      queryClient.setQueryData(
        comisionesKeys.detail(restoredComision.id),
        restoredComision
      );
    },
  });
};

/**
 * Hook to assign tutors to a comision
 */
export const useAssignTutores = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, tutores }: { id: number; tutores: TutoresAssign }) =>
      comisionesService.assignTutores(id, tutores),
    onSuccess: (_, { id }) => {
      // Invalidate the specific comision to refetch with updated tutores
      queryClient.invalidateQueries({ queryKey: comisionesKeys.detail(id) });
      // Also invalidate lists as they show num_tutores
      queryClient.invalidateQueries({ queryKey: comisionesKeys.lists() });
    },
  });
};
