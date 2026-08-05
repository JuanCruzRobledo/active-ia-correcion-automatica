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
import { entregasKeys } from '@/features/entregas/hooks/useEntregas';
import type { Correccion, CorreccionUpdate } from '../types';
// IA-012: corregir/recorregir devuelven 202 (corrección en background); marcamos
// la entrega en PENDIENTE (optimista) para que arranque el polling de la lista.
import type { CorreccionAceptadaResponse, EntregaList } from '@/features/entregas/types';

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
 * Handle API Key invalid error (Gemini u OpenRouter, según el proveedor activo):
 * actualiza localStorage y muestra el mensaje del backend, que ya nombra al
 * proveedor correcto (ver error_catalog.py — no hardcodear "Gemini" acá).
 */
function handleGeminiApiKeyError(
  queryClient: ReturnType<typeof useQueryClient>,
  error: unknown
): void {
  invalidateStoredApiKey();
  queryClient.invalidateQueries({ queryKey: ['me'] });
  toast.error(
    `❌ ${getErrorMessage(error, 'Tu API Key expiró o es inválida. Generá una nueva y actualizala en tu perfil.')}`,
    { duration: 10000 }
  );
}

/**
 * Handle rate-limit error (Gemini u OpenRouter): muestra el mensaje del
 * backend, que ya nombra al proveedor correcto.
 */
function handleGeminiRateLimitError(error: unknown): void {
  toast.error(
    `⏳ ${getErrorMessage(error, 'Se alcanzó el límite de uso de la API. Esperá unos minutos antes de volver a intentar.')}`,
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

  return useMutation<CorreccionAceptadaResponse, Error, number>({
    mutationFn: correccionesService.corregirEntrega,
    onSuccess: (_res, entregaId) => {
      // IA-012: la corrección corre en background (202). Marcamos la entrega en
      // PENDIENTE (optimista) para que el polling de la lista la lleve a
      // CORREGIDA/ERROR. No invalidamos: un refetch inmediato pisaría el PENDIENTE
      // optimista con el estado aún sin reclamar y frenaría el polling.
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

      toast.success('Corrección iniciada. El estado se actualizará automáticamente.');
    },
    onError: (error) => {
      if (isGeminiApiKeyError(error)) {
        handleGeminiApiKeyError(queryClient, error);
        return;
      }
      if (isGeminiRateLimitError(error)) {
        handleGeminiRateLimitError(error);
        return;
      }
      const msg = getErrorMessage(error, 'Error al corregir la entrega. Intenta nuevamente.');
      console.error('Error al corregir entrega:', error);
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

      // PERF-018: solo las listas (para mostrar "editado_manualmente").
      queryClient.invalidateQueries({ queryKey: entregasKeys.lists() });

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

  return useMutation<CorreccionAceptadaResponse, Error, number>({
    mutationFn: correccionesService.recorregirEntrega,
    onSuccess: (_res, entregaId) => {
      // IA-012: la re-corrección corre en background (202). Marcamos PENDIENTE
      // (optimista) para que el polling la lleve a CORREGIDA/ERROR (ver comentario
      // en useCorregirEntrega sobre por qué no invalidamos acá).
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

      toast.success('Re-corrección iniciada. El estado se actualizará automáticamente.');
    },
    onError: (error) => {
      if (isGeminiApiKeyError(error)) {
        handleGeminiApiKeyError(queryClient, error);
        return;
      }
      if (isGeminiRateLimitError(error)) {
        handleGeminiRateLimitError(error);
        return;
      }
      const msg = getErrorMessage(error, 'Error al re-corregir la entrega. Intenta nuevamente.');
      console.error('Error al re-corregir entrega:', error);
      toast.error(msg, { duration: 6000 });
    },
  });
};
