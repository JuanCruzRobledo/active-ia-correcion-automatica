/**
 * Dashboard hooks - React Query hooks for dashboard statistics.
 *
 * Ref: .claude/rules/frontend.md - React Query patterns
 */

import { useQuery } from '@tanstack/react-query';
import { dashboardService } from '../services/dashboard-service';
import type { AdminStats, CoordinadorStats, TutorStats } from '../types';

/**
 * Hook to fetch admin dashboard statistics.
 *
 * @returns React Query result with admin stats
 */
export const useDashboardAdminStats = () => {
  return useQuery<AdminStats>({
    queryKey: ['dashboard', 'admin', 'stats'],
    queryFn: dashboardService.getAdminStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch coordinador dashboard statistics.
 *
 * @returns React Query result with coordinador stats
 */
export const useDashboardCoordinadorStats = () => {
  return useQuery<CoordinadorStats>({
    queryKey: ['dashboard', 'coordinador', 'stats'],
    queryFn: dashboardService.getCoordinadorStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch tutor dashboard statistics.
 *
 * @returns React Query result with tutor stats
 */
export const useDashboardTutorStats = () => {
  return useQuery<TutorStats>({
    queryKey: ['dashboard', 'tutor', 'stats'],
    queryFn: dashboardService.getTutorStats,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};
