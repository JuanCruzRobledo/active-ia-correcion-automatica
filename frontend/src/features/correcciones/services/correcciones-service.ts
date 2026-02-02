// features/correcciones/services/correcciones-service.ts
/**
 * Service layer for correcciones (corrections) API.
 * Handles all HTTP requests related to corrections.
 *
 * Ref: skills/correccion-ia/SKILL.md - API Endpoints
 */

import { apiClient } from '@/shared/services/api-client';
import type { Correccion, CorreccionUpdate, CorregirLoteRequest } from '../types';

/**
 * Corrige una entrega individual con IA.
 *
 * @param entregaId - ID de la entrega a corregir
 * @returns Promise con la corrección generada
 */
export const corregirEntrega = async (entregaId: number): Promise<Correccion> => {
  const response = await apiClient.post<Correccion>(
    `/entregas/${entregaId}/corregir`
  );
  return response.data;
};

/**
 * Corrige múltiples entregas en lote.
 *
 * @param entregaIds - Array de IDs de entregas a corregir (máximo 50)
 * @returns Promise con array de correcciones generadas
 */
export const corregirEntregasLote = async (
  entregaIds: number[]
): Promise<Correccion[]> => {
  const response = await apiClient.post<Correccion[]>('/entregas/corregir-lote', {
    entrega_ids: entregaIds,
  } as CorregirLoteRequest);
  return response.data;
};

/**
 * Obtiene una corrección por ID.
 *
 * @param correccionId - ID de la corrección
 * @returns Promise con la corrección
 */
export const getCorreccionById = async (correccionId: number): Promise<Correccion> => {
  const response = await apiClient.get<Correccion>(`/correcciones/${correccionId}`);
  return response.data;
};

/**
 * Obtiene la corrección de una entrega.
 *
 * @param entregaId - ID de la entrega
 * @returns Promise con la corrección o null si no existe
 */
export const getCorreccionByEntregaId = async (
  entregaId: number
): Promise<Correccion | null> => {
  try {
    const response = await apiClient.get<Correccion>(
      `/entregas/${entregaId}/correccion`
    );
    return response.data;
  } catch (error) {
    // Si no existe corrección, retornar null
    return null;
  }
};

/**
 * Edita manualmente una corrección existente.
 *
 * @param correccionId - ID de la corrección a editar
 * @param data - Datos a actualizar (nota, criterios, fortalezas, etc.)
 * @returns Promise con la corrección actualizada
 */
export const updateCorreccion = async (
  correccionId: number,
  data: CorreccionUpdate
): Promise<Correccion> => {
  const response = await apiClient.put<Correccion>(
    `/correcciones/${correccionId}`,
    data
  );
  return response.data;
};

/**
 * Re-corrige una entrega (descarta corrección anterior y genera nueva).
 *
 * @param entregaId - ID de la entrega a re-corregir
 * @returns Promise con la nueva corrección generada
 */
export const recorregirEntrega = async (entregaId: number): Promise<Correccion> => {
  // Re-corregir usa el mismo endpoint que corregir
  // El backend se encarga de descartar la corrección anterior
  return corregirEntrega(entregaId);
};
