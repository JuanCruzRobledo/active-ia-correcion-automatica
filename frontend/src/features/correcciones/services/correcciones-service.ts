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
      `/correcciones/entregas/${entregaId}`
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
 * Re-corrige una entrega (reemplaza corrección anterior con nueva generada por IA).
 *
 * La corrección anterior se mantiene intacta hasta que la nueva esté validada y lista.
 * Si N8N falla o la respuesta de IA es inválida, la corrección anterior NO se pierde.
 *
 * Flujo del backend:
 * 1. Cambia estado a PENDIENTE
 * 2. Llama a N8N/Gemini para generar nueva corrección
 * 3. Si falla → marca ERROR, mantiene corrección anterior
 * 4. Si éxito → valida respuesta
 * 5. Si validación falla → marca ERROR, mantiene corrección anterior
 * 6. Solo si todo OK → borra corrección anterior y crea nueva
 *
 * @param entregaId - ID de la entrega a re-corregir
 * @returns Promise con la nueva corrección generada
 */
export const recorregirEntrega = async (entregaId: number): Promise<Correccion> => {
  const response = await apiClient.post<Correccion>(
    `/correcciones/entregas/${entregaId}/recorregir`
  );
  return response.data;
};

// --- Descarga de documentos ---

const downloadBlob = (blob: Blob, filename: string) => {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

/**
 * Descarga el PDF de devolución de una entrega corregida.
 * Obtiene primero la corrección para sacar su ID, luego descarga el PDF.
 */
export const descargarPDFCorreccion = async (entregaId: number): Promise<void> => {
  const correccion = await getCorreccionByEntregaId(entregaId);
  if (!correccion) {
    throw new Error('No se encontró corrección para esta entrega');
  }
  const response = await apiClient.get(`/documentos/correcciones/${correccion.id}/pdf`, {
    responseType: 'blob',
  });
  downloadBlob(response.data as Blob, `devolucion_entrega_${entregaId}.pdf`);
};

/**
 * Descarga un ZIP con todos los PDFs de devolución de una comisión/rúbrica.
 */
export const descargarTodosPDFs = async (comisionId: number, rubricaId: number): Promise<void> => {
  const response = await apiClient.get(
    `/documentos/comisiones/${comisionId}/rubricas/${rubricaId}/pdfs`,
    {
      responseType: 'blob',
      timeout: 180000, // 3 minutos para archivos grandes
    }
  );

  // Validar que el blob no esté vacío
  if (!(response.data instanceof Blob) || response.data.size === 0) {
    throw new Error('No se encontraron entregas corregidas o el archivo está vacío');
  }

  downloadBlob(response.data as Blob, `devoluciones_comision_${comisionId}_rubrica_${rubricaId}.zip`);
};

/**
 * Exporta las notas de una comisión/rúbrica en formato Excel.
 */
export const exportarExcel = async (comisionId: number, rubricaId: number): Promise<void> => {
  const response = await apiClient.get(
    `/documentos/comisiones/${comisionId}/rubricas/${rubricaId}/excel`,
    { responseType: 'blob' }
  );
  downloadBlob(response.data as Blob, `notas_comision_${comisionId}_rubrica_${rubricaId}.xlsx`);
};
