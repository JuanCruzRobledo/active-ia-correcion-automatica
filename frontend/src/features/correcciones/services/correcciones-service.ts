// features/correcciones/services/correcciones-service.ts
/**
 * Service layer for correcciones (corrections) API.
 * Handles all HTTP requests related to corrections.
 *
 * Ref: skills/correccion-ia/SKILL.md - API Endpoints
 */

import { isAxiosError } from 'axios';
import { apiClient } from '@/shared/services/api-client';
import type { Correccion, CorreccionUpdate } from '../types';

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
    // ERR-006: null SOLO cuando el backend confirma que no hay corrección (404).
    // Cualquier otro error (500, 403, timeout, red caída) se re-lanza para que
    // React Query lo exponga como isError y la UI distinga "sin corrección" de
    // "no pude consultar".
    if (isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw error;
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

export interface RubricaContext {
  tipo: string;
  numero: number | string;
}

/**
 * Sanitiza un string para usarlo en nombres de archivo:
 * - Remueve acentos/diacríticos
 * - Reemplaza espacios por guiones
 * - Elimina caracteres no permitidos en nombres de archivo
 */
const sanitizeFilename = (text: string): string =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '') // strip diacritics
    .replace(/\s+/g, '-')
    .replace(/[^a-zA-Z0-9\-_]/g, '')
    .replace(/-{2,}/g, '-')
    .replace(/^-|-$/g, '');

/**
 * Descarga el PDF de devolución de una entrega corregida.
 * Nombre resultante: NombreAlumno-Devolucion-TIPO_NUMERO.pdf
 *
 * @param entregaId - ID de la entrega
 * @param rubrica   - Contexto de la rúbrica para incluir tipo/número en el nombre del archivo
 * @param alumnoNombre - Nombre del alumno para incluir en el nombre del archivo
 */
export const descargarPDFCorreccion = async (
  entregaId: number,
  rubrica?: RubricaContext,
  alumnoNombre?: string
): Promise<void> => {
  const correccion = await getCorreccionByEntregaId(entregaId);
  if (!correccion) {
    throw new Error('No se encontró corrección para esta entrega');
  }
  const response = await apiClient.get(`/documentos/correcciones/${correccion.id}/pdf`, {
    responseType: 'blob',
  });

  const alumnoPart = alumnoNombre ? sanitizeFilename(alumnoNombre) : `entrega-${entregaId}`;
  const rubricaPart = rubrica
    ? `${rubrica.tipo}-${rubrica.numero}`.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9\-_]/g, '')
    : '';

  const filename = rubricaPart
    ? `${alumnoPart}-Devolucion-${rubricaPart}.pdf`
    : `${alumnoPart}-Devolucion.pdf`;

  downloadBlob(response.data as Blob, filename);
};

/**
 * Descarga un ZIP con todos los PDFs de devolución de una comisión/rúbrica.
 * Nombre resultante: Devoluciones-TIPO-NUMERO-NombreComision.zip
 *
 * @param comisionId   - ID de la comisión
 * @param rubricaId    - ID de la rúbrica
 * @param rubrica      - Contexto de la rúbrica para incluir tipo/número en el nombre del ZIP
 * @param comisionNombre - Nombre de la comisión para incluir en el nombre del ZIP
 */
export const descargarTodosPDFs = async (
  comisionId: number,
  rubricaId: number,
  rubrica?: RubricaContext,
  comisionNombre?: string
): Promise<void> => {
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

  const rubricaPart = rubrica
    ? `${rubrica.tipo}-${rubrica.numero}`.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9\-_]/g, '')
    : `rubrica-${rubricaId}`;

  const comisionPart = comisionNombre
    ? sanitizeFilename(comisionNombre)
    : `comision-${comisionId}`;

  const filename = `Devoluciones-${rubricaPart}-${comisionPart}.zip`;

  downloadBlob(response.data as Blob, filename);
};

/**
 * Descarga un ZIP con los PDFs de devolución de las entregas seleccionadas (solo CORREGIDA).
 */
export const descargarPDFsSeleccionados = async (
  entregaIds: number[],
  rubrica?: RubricaContext,
  comisionNombre?: string
): Promise<void> => {
  const response = await apiClient.post(
    '/documentos/pdfs-seleccionados',
    { entrega_ids: entregaIds },
    { responseType: 'blob', timeout: 180000 }
  );

  if (!(response.data instanceof Blob) || response.data.size === 0) {
    throw new Error('No se encontraron entregas corregidas o el archivo está vacío');
  }

  const rubricaPart = rubrica
    ? `${rubrica.tipo}-${rubrica.numero}`.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9\-_]/g, '')
    : 'seleccionados';

  const comisionPart = comisionNombre ? sanitizeFilename(comisionNombre) : '';

  const filename = comisionPart
    ? `Devoluciones-Seleccionados-${rubricaPart}-${comisionPart}.zip`
    : `Devoluciones-Seleccionados-${rubricaPart}.zip`;

  downloadBlob(response.data as Blob, filename);
};

/**
 * Exporta las notas de una comisión/rúbrica en formato Excel.
 */
export const exportarExcel = async (comisionId: number, rubricaId: number): Promise<void> => {
  const response = await apiClient.get(
    `/documentos/comisiones/${comisionId}/rubricas/${rubricaId}/excel`,
    { responseType: 'blob' }
  );

  // Extract filename from Content-Disposition header
  const contentDisposition = response.headers['content-disposition'];
  let filename = `notas_comision_${comisionId}_rubrica_${rubricaId}.xlsx`; // fallback

  if (contentDisposition) {
    const filenameMatch = contentDisposition.match(/filename="([^"]+)"/);
    if (filenameMatch && filenameMatch[1]) {
      filename = filenameMatch[1];
    }
  }

  downloadBlob(response.data as Blob, filename);
};
