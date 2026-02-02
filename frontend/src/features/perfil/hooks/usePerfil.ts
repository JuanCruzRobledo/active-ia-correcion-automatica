// features/perfil/hooks/usePerfil.ts
/**
 * React Query hooks for user profile operations.
 *
 * Provides hooks for querying and mutating user profile with automatic
 * cache management.
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import * as perfilService from '../services/perfil-service';
import type { UserProfile } from '../types';

/**
 * Query key factory for profile cache management.
 */
export const perfilKeys = {
  all: ['perfil'] as const,
  detail: () => [...perfilKeys.all, 'detail'] as const,
};

/**
 * Hook to get current user's profile.
 *
 * @returns Query result with profile data
 */
export const useProfile = () => {
  return useQuery<UserProfile, Error>({
    queryKey: perfilKeys.detail(),
    queryFn: () => perfilService.getProfile(),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

/**
 * Hook to update Gemini API Key.
 *
 * Invalidates profile cache on success.
 *
 * @returns Mutation hook for updating API Key
 */
export const useUpdateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<
    { message: string; valid: boolean },
    Error,
    string
  >({
    mutationFn: (apiKey: string) => perfilService.updateApiKey(apiKey),
    onSuccess: (response) => {
      // Invalidate profile to refetch with updated API Key status
      queryClient.invalidateQueries({ queryKey: perfilKeys.all });

      if (response.valid) {
        toast.success('API Key configurada y validada exitosamente');
      } else {
        toast.error('API Key inválida. Verifica e intenta nuevamente.');
      }
    },
    onError: (error) => {
      console.error('Error al actualizar API Key:', error);
      toast.error(
        error.message || 'Error al configurar API Key. Intenta nuevamente.'
      );
    },
  });
};
