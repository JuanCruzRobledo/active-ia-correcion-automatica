/**
 * Actividades hooks - React Query hooks for activity/audit log.
 *
 * Ref: docs/specs/15-ACTIVIDAD-RECIENTE-AUDITORIA.md
 * Ref: .claude/rules/frontend.md - React Query patterns
 */

import { useQuery } from '@tanstack/react-query';
import { actividadesService } from '../services/actividades-service';
import type { ActividadListResponse, TipoActividad } from '@/shared/types';

/**
 * Hook to fetch recent system activities.
 *
 * @param params - Query parameters
 * @param params.limit - Number of results to return (default: 10)
 * @param params.offset - Offset for pagination (default: 0)
 * @param params.tipo - Filter by activity type (optional)
 * @returns React Query result with recent activities
 */
export const useActividadesRecientes = (params?: {
  limit?: number;
  offset?: number;
  tipo?: TipoActividad;
}) => {
  return useQuery<ActividadListResponse>({
    queryKey: ['actividades', 'recientes', params],
    queryFn: () => actividadesService.getRecientes(params),
    staleTime: 30000, // 30 seconds - activities should be relatively fresh
  });
};
