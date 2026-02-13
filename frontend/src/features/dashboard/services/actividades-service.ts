/**
 * Actividades service - API calls for activity/audit log.
 *
 * Ref: backend/app/routers/actividades.py
 * Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
 */

import { apiClient } from '@/shared/services/api-client';
import type { ActividadListResponse, TipoActividad } from '@/shared/types';

export const actividadesService = {
  /**
   * Get recent system activities.
   * Endpoint: GET /api/v1/actividades/recientes
   *
   * @param params - Query parameters
   * @param params.limit - Number of results to return (default: 10, max: 50)
   * @param params.offset - Offset for pagination (default: 0)
   * @param params.tipo - Filter by activity type (optional)
   */
  getRecientes: async (params?: {
    limit?: number;
    offset?: number;
    tipo?: TipoActividad;
  }): Promise<ActividadListResponse> => {
    const searchParams = new URLSearchParams();

    if (params?.limit !== undefined) {
      searchParams.append('limit', params.limit.toString());
    }
    if (params?.offset !== undefined) {
      searchParams.append('offset', params.offset.toString());
    }
    if (params?.tipo) {
      searchParams.append('tipo', params.tipo);
    }

    const queryString = searchParams.toString();
    const url = queryString ? `/actividades/recientes?${queryString}` : '/actividades/recientes';

    const { data } = await apiClient.get<ActividadListResponse>(url);
    return data;
  },
};
