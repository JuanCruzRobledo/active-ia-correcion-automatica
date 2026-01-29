// React Query hooks for materias
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { materiasService } from '../services';
import type {
  MateriasFilters,
  MateriaCreate,
  MateriaUpdate,
  CoordinadoresAssign,
} from '../types';

// Query keys factory for cache management
export const materiasKeys = {
  all: ['materias'] as const,
  lists: () => [...materiasKeys.all, 'list'] as const,
  list: (filters?: MateriasFilters) => [...materiasKeys.lists(), filters] as const,
  details: () => [...materiasKeys.all, 'detail'] as const,
  detail: (id: number) => [...materiasKeys.details(), id] as const,
};

/**
 * Hook to fetch paginated list of materias with filters
 */
export const useMaterias = (filters?: MateriasFilters) => {
  return useQuery({
    queryKey: materiasKeys.list(filters),
    queryFn: () => materiasService.getAll(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch single materia by ID
 */
export const useMateria = (id: number) => {
  return useQuery({
    queryKey: materiasKeys.detail(id),
    queryFn: () => materiasService.getById(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });
};

/**
 * Hook to create new materia
 */
export const useCreateMateria = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: MateriaCreate) => materiasService.create(data),
    onSuccess: () => {
      // Invalidate all lists to refetch
      queryClient.invalidateQueries({ queryKey: materiasKeys.lists() });
    },
  });
};

/**
 * Hook to update existing materia
 */
export const useUpdateMateria = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: MateriaUpdate }) =>
      materiasService.update(id, data),
    onSuccess: (updatedMateria) => {
      // Update detail cache
      queryClient.setQueryData(
        materiasKeys.detail(updatedMateria.id),
        updatedMateria
      );
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: materiasKeys.lists() });
    },
  });
};

/**
 * Hook to soft delete materia
 */
export const useDeleteMateria = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => materiasService.delete(id),
    onSuccess: () => {
      // Invalidate all queries to refetch
      queryClient.invalidateQueries({ queryKey: materiasKeys.all });
    },
  });
};

/**
 * Hook to restore soft-deleted materia
 */
export const useRestoreMateria = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => materiasService.restore(id),
    onSuccess: (restoredMateria) => {
      // Update detail cache
      queryClient.setQueryData(
        materiasKeys.detail(restoredMateria.id),
        restoredMateria
      );
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: materiasKeys.lists() });
    },
  });
};

/**
 * Hook to assign coordinators to materia
 */
export const useAssignCoordinadores = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CoordinadoresAssign }) =>
      materiasService.assignCoordinadores(id, data),
    onSuccess: (_, variables) => {
      // Invalidate detail to refetch with new coordinators
      queryClient.invalidateQueries({ queryKey: materiasKeys.detail(variables.id) });
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: materiasKeys.lists() });
    },
  });
};
