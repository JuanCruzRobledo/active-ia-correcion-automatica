// features/correcciones/hooks/useCorrecciones.ts
/**
 * React Query hooks for correcciones operations.
 *
 * Provides hooks for querying and mutating corrections with automatic
 * cache management and optimistic updates.
 *
 * Ref: skills/correccion-ia/SKILL.md - API Endpoints
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { AxiosError } from 'axios';
import * as correccionesService from '../services/correcciones-service';
import { invalidateStoredApiKey } from '@/features/auth/services/auth-service';
import type { Correccion, CorreccionUpdate } from '../types';

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
    'Las correcciones fueron detenidas. ' +
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
 * Query key factory for correcciones cache management.
 */
export const correccionesKeys = {
  all: ['correcciones'] as const,
  details: () => [...correccionesKeys.all, 'detail'] as const,
  detail: (id: number) => [...correccionesKeys.details(), id] as const,
  byEntrega: (entregaId: number) =>
    [...correccionesKeys.all, 'entrega', entregaId] as const,
};

/**
 * Hook to get a corrección by ID.
 *
 * @param correccionId - Corrección ID
 * @returns Query result with corrección detail
 */
export const useCorreccion = (correccionId: number) => {
  return useQuery<Correccion, Error>({
    queryKey: correccionesKeys.detail(correccionId),
    queryFn: () => correccionesService.getCorreccionById(correccionId),
    enabled: correccionId > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to get corrección by entrega ID.
 *
 * @param entregaId - Entrega ID
 * @returns Query result with corrección or null
 */
export const useCorreccionByEntrega = (entregaId: number) => {
  return useQuery<Correccion | null, Error>({
    queryKey: correccionesKeys.byEntrega(entregaId),
    queryFn: () => correccionesService.getCorreccionByEntregaId(entregaId),
    enabled: entregaId > 0,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to correct a single entrega with AI.
 *
 * Invalidates entregas list and corrección cache on success.
 *
 * @returns Mutation hook for correcting entrega
 */
export const useCorregirEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation<Correccion, Error, number>({
    mutationFn: correccionesService.corregirEntrega,
    onSuccess: (correccion) => {
      // Invalidate entregas list to update estado
      queryClient.invalidateQueries({ queryKey: ['entregas'] });

      // Set the new corrección in cache
      queryClient.setQueryData(
        correccionesKeys.detail(correccion.id),
        correccion
      );
      queryClient.setQueryData(
        correccionesKeys.byEntrega(correccion.entrega_id),
        correccion
      );

      toast.success('Entrega corregida exitosamente');
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
 * Hook to correct multiple entregas in batch.
 *
 * Invalidates entregas list on success.
 *
 * @returns Mutation hook for batch correction
 */
export const useCorregirEntregasLote = () => {
  const queryClient = useQueryClient();

  return useMutation<Correccion[], Error, number[]>({
    mutationFn: correccionesService.corregirEntregasLote,
    onSuccess: (correcciones) => {
      // Invalidate entregas list to update estados
      queryClient.invalidateQueries({ queryKey: ['entregas'] });

      // Set each corrección in cache
      correcciones.forEach((correccion) => {
        queryClient.setQueryData(
          correccionesKeys.detail(correccion.id),
          correccion
        );
        queryClient.setQueryData(
          correccionesKeys.byEntrega(correccion.entrega_id),
          correccion
        );
      });

      toast.success(
        `${correcciones.length} entrega(s) corregida(s) exitosamente`
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
      const msg = getErrorMessage(error, 'Error al corregir las entregas. Intenta nuevamente.');
      console.error('Error al corregir entregas en lote:', error);
      toast.error(msg, { duration: 6000 });
    },
  });
};

/**
 * Hook to update/edit an existing corrección.
 *
 * Invalidates corrección cache on success.
 *
 * @returns Mutation hook for updating corrección
 */
export const useUpdateCorreccion = () => {
  const queryClient = useQueryClient();

  return useMutation<
    Correccion,
    Error,
    { correccionId: number; data: CorreccionUpdate }
  >({
    mutationFn: ({ correccionId, data }) =>
      correccionesService.updateCorreccion(correccionId, data),
    onSuccess: (updatedCorreccion) => {
      // Update corrección in cache
      queryClient.setQueryData(
        correccionesKeys.detail(updatedCorreccion.id),
        updatedCorreccion
      );
      queryClient.setQueryData(
        correccionesKeys.byEntrega(updatedCorreccion.entrega_id),
        updatedCorreccion
      );

      // Invalidate entregas list to show "editado_manualmente"
      queryClient.invalidateQueries({ queryKey: ['entregas'] });

      toast.success('Corrección actualizada exitosamente');
    },
    onError: (error) => {
      console.error('Error al actualizar corrección:', error);
      toast.error('Error al actualizar la corrección. Intenta nuevamente.');
    },
  });
};

/**
 * Hook to re-correct an entrega (discards previous correction).
 *
 * Invalidates entregas list and corrección cache on success.
 *
 * @returns Mutation hook for re-correcting entrega
 */
export const useRecorregirEntrega = () => {
  const queryClient = useQueryClient();

  return useMutation<Correccion, Error, number>({
    mutationFn: correccionesService.recorregirEntrega,
    onSuccess: (correccion) => {
      // Invalidate entregas list
      queryClient.invalidateQueries({ queryKey: ['entregas'] });

      // Update corrección in cache
      queryClient.setQueryData(
        correccionesKeys.detail(correccion.id),
        correccion
      );
      queryClient.setQueryData(
        correccionesKeys.byEntrega(correccion.entrega_id),
        correccion
      );

      toast.success('Entrega re-corregida exitosamente');
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
      const msg = getErrorMessage(error, 'Error al re-corregir la entrega. Intenta nuevamente.');
      console.error('Error al re-corregir entrega:', error);
      toast.error(msg, { duration: 6000 });
    },
  });
};
