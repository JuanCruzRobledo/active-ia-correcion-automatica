// features/entregas/services/entregas-service.ts
/**
 * Service for entregas API operations.
 *
 * Handles individual and bulk upload of student submissions,
 * with file consolidation and processing.
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 7
 */

import { apiClient } from '@/shared/services/api-client';
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
  Correccion,
  CorregirLoteAceptadoResponse,
} from '../types';


export const entregasService = {
  /**
   * Get all entregas with optional filters and pagination.
   */
  getAll: async (filters: EntregasFilters): Promise<EntregaList> => {
    const params = new URLSearchParams();

    params.append('comision_id', filters.comision_id.toString());
    params.append('rubrica_id', filters.rubrica_id.toString());

    if (filters.estado) {
      params.append('estado', filters.estado);
    }

    if (filters.search) {
      params.append('search', filters.search);
    }

    if (filters.solo_archivadas) {
      params.append('solo_archivadas', 'true');
    }

    if (filters.fecha_desde) {
      params.append('fecha_desde', filters.fecha_desde);
    }

    if (filters.fecha_hasta) {
      params.append('fecha_hasta', filters.fecha_hasta);
    }

    if (filters.page) {
      params.append('page', filters.page.toString());
    }

    if (filters.per_page) {
      params.append('per_page', filters.per_page.toString());
    }

    const { data } = await apiClient.get<EntregaList>(
      `/entregas?${params.toString()}`
    );
    return data;
  },

  /**
   * Get a single entrega by ID with full details.
   */
  getById: async (id: number): Promise<EntregaDetail> => {
    const { data } = await apiClient.get<EntregaDetail>(`/entregas/${id}`);
    return data;
  },

  /**
   * Create a new individual entrega.
   * Uses FormData for file upload.
   */
  create: async (entregaData: EntregaCreate): Promise<Entrega> => {
    const formData = new FormData();

    formData.append('comision_id', entregaData.comision_id.toString());
    formData.append('rubrica_id', entregaData.rubrica_id.toString());
    formData.append('alumno_nombre', entregaData.alumno_nombre);
    formData.append('archivo', entregaData.archivo);

    if (entregaData.modo_consolidacion) {
      formData.append('modo_consolidacion', entregaData.modo_consolidacion);
    }

    if (entregaData.extensiones_personalizadas) {
      formData.append(
        'extensiones_personalizadas',
        JSON.stringify(entregaData.extensiones_personalizadas)
      );
    }

    if (entregaData.sobrescribir !== undefined) {
      formData.append('sobrescribir', entregaData.sobrescribir.toString());
    }

    if (entregaData.moodle_url) {
      formData.append('moodle_url', entregaData.moodle_url);
    }

    const { data } = await apiClient.post<Entrega>('/entregas', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return data;
  },

  /**
   * Create multiple entregas from a ZIP file (bulk upload).
   * Uses FormData for file upload.
   */
  createMasiva: async (
    cargaMasivaData: CargaMasivaCreate
  ): Promise<CargaMasivaResponse> => {
    const formData = new FormData();

    formData.append('comision_id', cargaMasivaData.comision_id.toString());
    formData.append('rubrica_id', cargaMasivaData.rubrica_id.toString());
    formData.append('archivo_zip', cargaMasivaData.archivo_zip);
    formData.append('modo_consolidacion', cargaMasivaData.modo_consolidacion);
    formData.append('sobrescribir', cargaMasivaData.sobrescribir.toString());

    if (cargaMasivaData.extensiones_personalizadas) {
      formData.append(
        'extensiones_personalizadas',
        JSON.stringify(cargaMasivaData.extensiones_personalizadas)
      );
    }

    const { data } = await apiClient.post<CargaMasivaResponse>(
      '/entregas/masiva',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return data;
  },

  /**
   * Soft delete an entrega.
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/entregas/${id}`);
  },

  /**
   * Get the full consolidated code content of an entrega.
   */
  getContenido: async (id: number): Promise<EntregaContenido> => {
    const { data } = await apiClient.get<EntregaContenido>(
      `/entregas/${id}/contenido`
    );
    return data;
  },

  /**
   * Trigger AI correction for a specific entrega.
   */
  corregir: async (id: number): Promise<Correccion> => {
    const { data } = await apiClient.post<Correccion>(`/correcciones/entregas/${id}/corregir`);
    return data;
  },

  /**
   * Trigger AI correction for multiple entregas.
   */
  corregirLote: async (ids: number[]): Promise<CorregirLoteAceptadoResponse> => {
    const { data } = await apiClient.post<CorregirLoteAceptadoResponse>('/correcciones/lote', {
      entrega_ids: ids,
    });
    return data;
  },

  /**
   * Archive or unarchive multiple entregas.
   * Archived entregas are hidden from the default list (visible only with include_archivadas=true).
   */
  archivar: async (ids: number[], archivado = true): Promise<EntregaAccionMasivaResponse> => {
    const { data } = await apiClient.patch<EntregaAccionMasivaResponse>('/entregas/archivar', {
      ids,
      archivado,
    });
    return data;
  },

  /**
   * Bulk hard delete multiple entregas.
   */
  deleteMasivo: async (ids: number[]): Promise<EntregaAccionMasivaResponse> => {
    const { data } = await apiClient.delete<EntregaAccionMasivaResponse>('/entregas/masivo', {
      data: { ids },
    });
    return data;
  },

};
