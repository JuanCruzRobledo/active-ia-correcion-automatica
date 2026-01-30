// features/entregas/hooks/useEntregas.ts
/**
 * React Query hooks for entregas operations.
 *
 * Provides hooks for querying and mutating entregas with automatic
 * cache management and optimistic updates.
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 7
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { entregasService } from '../services/entregas-service';
import type {
  Entrega,
  EntregaDetail,
  EntregaList,
  EntregaCreate,
  CargaMasivaCreate,
  CargaMasivaResponse,
  EntregaContenido,
  EntregasFilters,
  Correccion,
} from '../types';

/**
 * Query key factory for entregas cache management.
 */
export const entregasKeys = {
  all: ['entregas'] as const,
  lists: () => [...entregasKeys.all, 'list'] as const,
  list: (filters: EntregasFilters) =>
    [...entregasKeys.lists(), filters] as const,
  details: () => [...entregasKeys.all, 'detail'] as const,
  detail: (id: number) => [...entregasKeys.details(), id] as const,
  contenidos: () => [...entregasKeys.all, 'contenido'] as const,
  contenido: (id: number) => [...entregasKeys.contenidos(), id] as const,
};

/**
 * Hook to get a list of entregas with filters.
 *
 * @param filters - Query filters (comision_id, rubrica_id, estado, search, pagination)
 * @param options - Additional query options (e.g., enabled)
 * @returns Query result with entregas list
 */
export const useEntregas = (
  filters?: EntregasFilters,
  options?: { enabled?: boolean }
) => {
  return useQuery<EntregaList, Error>({
    queryKey: entregasKeys.list(filters ?? { comision_id: 0, rubrica_id: 0 }),
    queryFn: () => entregasService.getAll(filters!),
    staleTime: 5 * 60 * 1000, // 5 minutes
    enabled: options?.enabled ?? !!filters,
  });
};

/**
 * Hook to get a single entrega by ID with full details.
 *
 * @param id - Entrega ID
 * @returns Query result with entrega detail
 */
export const useEntrega = (id: number) => {
  return useQuery<EntregaDetail, Error>({
    queryKey: entregasKeys.detail(id),
    queryFn: () => entregasService.getById(id),
    enabled: id > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to get the full code content of an entrega.
 *
 * @param id - Entrega ID
 * @returns Query result with code content
 */
export const useEntregaContenido = (id: number) => {
  return useQuery<EntregaContenido, Error>({
    queryKey: entregasKeys.contenido(id),
    queryFn: () => entregasService.getContenido(id),
    enabled: id > 0,
    staleTime: 10 * 60 * 1000, // 10 minutes (content rarely changes)
  });
};

/**
 * Hook to create a new individual entrega.
 *
 * Invalidates entregas lists on success.
 *
 * @returns Mutation hook for creating entrega
 */
export const useCreateEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation<Entrega, Error, EntregaCreate>({
    mutationFn: entregasService.create,
    onSuccess: (newEntrega) => {
      // Invalidate all lists that might include this entrega
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });

      // Optionally set the new entrega in cache
      queryClient.setQueryData(
        entregasKeys.detail(newEntrega.id),
        newEntrega
      );
    },
  });
};

/**
 * Hook to create multiple entregas from a ZIP file (bulk upload).
 *
 * Invalidates entregas lists on success.
 *
 * @returns Mutation hook for bulk upload
 */
export const useCreateEntregaMasiva = () => {
  const queryClient = useQueryClient();

  return useMutation<CargaMasivaResponse, Error, CargaMasivaCreate>({
    mutationFn: entregasService.createMasiva,
    onSuccess: () => {
      // Invalidate all lists since multiple entregas were created
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });
    },
  });
};

/**
 * Hook to delete an entrega (soft delete).
 *
 * Invalidates entregas lists and removes detail from cache on success.
 *
 * @returns Mutation hook for deleting entrega
 */
export const useDeleteEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, number>({
    mutationFn: entregasService.delete,
    onSuccess: (_, deletedId) => {
      // Invalidate all lists
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });

      // Remove detail from cache
      queryClient.removeQueries({
        queryKey: entregasKeys.detail(deletedId),
      });

      // Remove contenido from cache
      queryClient.removeQueries({
        queryKey: entregasKeys.contenido(deletedId),
      });
    },
  });

};

/**
 * Hook to trigger AI correction for an entrega.
 *
 * Invalidates entregas lists and updates detail cache on success.
 */
export const useCorregirEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation<Correccion, Error, number>({
    mutationFn: entregasService.corregir,
    onSuccess: (correccion, entregaId) => {
      // Invalidate lists
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });

      // Update detail if it exists in cache
      queryClient.setQueryData<EntregaDetail>(
        entregasKeys.detail(entregaId),
        (old) => {
          if (!old) return undefined;
          return {
            ...old,
            estado: 'CORREGIDA',
            correccion: {
              id: correccion.id,
              nota: correccion.nota,
              editado_manualmente: correccion.editado_manualmente,
              fecha_correccion: correccion.fecha_correccion,
            },
          };
        }
      );
    },
  });
};

/**
 * Hook to trigger AI correction for multiple entregas.
 *
 * Invalidates entregas lists on success.
 */
export const useCorregirEntregaMasiva = () => {
  const queryClient = useQueryClient();

  return useMutation<Correccion[], Error, number[]>({
    mutationFn: entregasService.corregirLote,
    onSuccess: () => {
      // Invalidate all lists
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });
    },
  });
};

