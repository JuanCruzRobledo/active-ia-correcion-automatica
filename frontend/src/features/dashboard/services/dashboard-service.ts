/**
 * Dashboard service - API calls for dashboard statistics.
 *
 * Ref: backend/app/routers/dashboard.py
 */

import { apiClient } from '@/shared/services/api-client';
import type { AdminStats, CoordinadorStats, TutorStats } from '../types';

export const dashboardService = {
  /**
   * Get admin dashboard statistics.
   * Endpoint: GET /api/v1/dashboard/admin/stats
   */
  getAdminStats: async (): Promise<AdminStats> => {
    const { data } = await apiClient.get<AdminStats>('/dashboard/admin/stats');
    return data;
  },

  /**
   * Get coordinador dashboard statistics.
   * Endpoint: GET /api/v1/dashboard/coordinador/stats
   */
  getCoordinadorStats: async (): Promise<CoordinadorStats> => {
    const { data } = await apiClient.get<CoordinadorStats>('/dashboard/coordinador/stats');
    return data;
  },

  /**
   * Get tutor dashboard statistics.
   * Endpoint: GET /api/v1/dashboard/tutor/stats
   */
  getTutorStats: async (): Promise<TutorStats> => {
    const { data } = await apiClient.get<TutorStats>('/dashboard/tutor/stats');
    return data;
  },
};
