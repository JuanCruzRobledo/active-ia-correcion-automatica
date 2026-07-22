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
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';
import { entregasService } from '../services/entregas-service';
import { invalidateStoredApiKey } from '@/features/auth/services/auth-service';
import type {
  Entrega,
  EntregaDetail,
  EntregaList,
  EntregaCreate,
  CargaMasivaCreate,
  CargaMasivaResponse,
  EntregaContenido,
  EntregasFilters,
  EntregaAccionMasivaResponse,
  CorregirLoteAceptadoResponse,
  CorreccionAceptadaResponse,
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
 * Check if an error is a Gemini API Key invalid error (HTTP 402).
 */
function isGeminiApiKeyError(error: unknown): boolean {
  if (error instanceof AxiosError && error.response?.status === 402) {
    const detail = error.response.data?.detail;
    if (typeof detail === 'object' && detail?.error_code === 'GEMINI_API_KEY_INVALID') {
      return true;
    }
  }
  return false;
}

/**
 * Check if an error is a Gemini rate-limit error (HTTP 429).
 */
function isGeminiRateLimitError(error: unknown): boolean {
  if (error instanceof AxiosError && error.response?.status === 429) {
    const detail = error.response.data?.detail;
    if (typeof detail === 'object' && detail?.error_code === 'GEMINI_RATE_LIMIT') {
      return true;
    }
  }
  return false;
}

/**
 * Handle Gemini API Key invalid error: update localStorage and show toast.
 */
function handleGeminiApiKeyError(queryClient: ReturnType<typeof useQueryClient>): void {
  invalidateStoredApiKey();
  queryClient.invalidateQueries({ queryKey: ['me'] });
  toast.error(
    '❌ Tu API Key de Gemini expiró o es inválida. Por favor generá una nueva en Google AI Studio con otra cuenta de Google y actualizala en tu perfil.',
    { duration: 10000 }
  );
}

/**
 * Handle Gemini rate-limit error: show clear toast.
 */
function handleGeminiRateLimitError(): void {
  toast.error(
    '⏳ Se alcanzó el límite de uso de la API de Gemini. ' +
    'Las correcciones en lote fueron detenidas. ' +
    'Esperá unos minutos antes de volver a intentar.',
    { duration: 10000 }
  );
}

/**
 * Extract a readable error message from an Axios error response.
 */
function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof AxiosError && error.response?.data?.detail) {
    const detail = error.response.data.detail;
    return typeof detail === 'string' ? detail : (detail?.message || fallback);
  }
  return fallback;
}

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

  return useMutation<CorreccionAceptadaResponse, Error, number>({
    mutationFn: entregasService.corregir,
    onSuccess: (_res, entregaId) => {
      // IA-012: la corrección corre en background (202). Marcamos la entrega en
      // PENDIENTE de forma optimista para que el polling de la lista (EntregasPage)
      // arranque y la lleve a CORREGIDA/ERROR. NO invalidamos acá: un refetch
      // inmediato podría pisar el PENDIENTE optimista con el SUBIDA todavía en DB
      // (el background aún no reclamó) y frenar el polling.
      queryClient.setQueriesData<EntregaList>(
        { queryKey: entregasKeys.lists() },
        (old) => {
          if (!old?.items) return old;
          return {
            ...old,
            items: old.items.map((e) =>
              e.id === entregaId ? { ...e, estado: 'PENDIENTE' } : e
            ),
          };
        }
      );
      queryClient.setQueryData<EntregaDetail>(
        entregasKeys.detail(entregaId),
        (old) => (old ? { ...old, estado: 'PENDIENTE' } : undefined)
      );
    },
    onError: (error) => {
      if (isGeminiApiKeyError(error)) {
        handleGeminiApiKeyError(queryClient);
        return;
      }
      if (isGeminiRateLimitError(error)) {
        handleGeminiRateLimitError();
        return;
      }
      const msg = getErrorMessage(error, 'Error al corregir la entrega. Intenta nuevamente.');
      console.error('Error al corregir entrega:', error);
      toast.error(msg, { duration: 6000 });
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

  return useMutation<CorregirLoteAceptadoResponse, Error, number[]>({
    mutationFn: entregasService.corregirLote,
    onSuccess: () => {
      // Invalidate all lists
      queryClient.invalidateQueries({
        queryKey: entregasKeys.lists(),
      });
    },
    onError: (error) => {
      if (isGeminiApiKeyError(error)) {
        handleGeminiApiKeyError(queryClient);
        return;
      }
      if (isGeminiRateLimitError(error)) {
        handleGeminiRateLimitError();
        return;
      }
      const msg = getErrorMessage(error, 'Error al corregir las entregas. Intenta nuevamente.');
      console.error('Error al corregir entregas en lote:', error);
      toast.error(msg, { duration: 6000 });
    },
  });
};

/**
 * Hook to archive or unarchive multiple entregas.
 *
 * Archived entregas are hidden from the default list view.
 * They appear only when include_archivadas=true (estado filter = TODOS).
 */
export const useArchivarEntregas = () => {
  const queryClient = useQueryClient();

  return useMutation<EntregaAccionMasivaResponse, Error, { ids: number[]; archivado?: boolean }>({
    mutationFn: ({ ids, archivado = true }) => entregasService.archivar(ids, archivado),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entregasKeys.lists() });
    },
    onError: (error) => {
      const msg = getErrorMessage(error, 'Error al archivar las entregas.');
      toast.error(msg, { duration: 5000 });
    },
  });
};

/**
 * Hook to bulk delete multiple entregas permanently.
 */
export const useDeleteEntregasMasivo = () => {
  const queryClient = useQueryClient();

  return useMutation<EntregaAccionMasivaResponse, Error, number[]>({
    mutationFn: entregasService.deleteMasivo,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: entregasKeys.lists() });
    },
    onError: (error) => {
      const msg = getErrorMessage(error, 'Error al eliminar las entregas.');
      toast.error(msg, { duration: 5000 });
    },
  });
};

