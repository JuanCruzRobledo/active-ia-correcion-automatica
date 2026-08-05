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
import { changePassword } from '../../auth/services/auth-service';
import type { UserProfile, CorrectionProvider } from '../types';
import type { ChangePasswordRequest } from '@/shared/types';

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
/**
 * Hook to change password from profile.
 * Does not navigate on success — the caller handles modal close.
 */
export const useChangePassword = () => {
  return useMutation<{ message: string }, Error, ChangePasswordRequest>({
    mutationFn: (data) => changePassword(data),
    onSuccess: () => {
      toast.success('Contraseña actualizada exitosamente');
    },
    onError: (error) => {
      toast.error(error.message || 'Error al cambiar contraseña');
    },
  });
};

export const useUpdateApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<
    { message: string; valid: boolean },
    Error,
    { apiKey: string; provider: CorrectionProvider }
  >({
    mutationFn: ({ apiKey, provider }) =>
      perfilService.updateApiKey(apiKey, provider),
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

/**
 * Hook para eliminar la API Key de un proveedor sin reemplazarla por otra.
 * Invalida el perfil: la key vuelve a mostrarse como "No configurada".
 */
export const useDeleteApiKey = () => {
  const queryClient = useQueryClient();

  return useMutation<
    { message: string; provider: CorrectionProvider },
    Error,
    CorrectionProvider
  >({
    mutationFn: (provider) => perfilService.deleteApiKey(provider),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: perfilKeys.all });
      toast.success('API Key eliminada');
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo eliminar la API Key');
    },
  });
};

/**
 * Hook para cambiar el modo de corrección activo (slider del perfil).
 * Invalida el perfil para reflejar el modo y la key correspondiente.
 */
export const useUpdateCorrectionProvider = () => {
  const queryClient = useQueryClient();

  return useMutation<
    { message: string; correction_provider: CorrectionProvider },
    Error,
    CorrectionProvider
  >({
    mutationFn: (provider) => perfilService.updateCorrectionProvider(provider),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: perfilKeys.all });
      toast.success(
        res.correction_provider === 'openrouter'
          ? 'Modo de corrección: OpenRouter (beta)'
          : 'Modo de corrección: Gemini Studio'
      );
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo cambiar el modo de corrección');
    },
  });
};

/**
 * Hook para setear el email de notificaciones del usuario.
 * Invalida el perfil para refrescar el valor mostrado.
 */
export const useUpdateEmail = () => {
  const queryClient = useQueryClient();

  return useMutation<{ message: string; email: string | null }, Error, string | null>({
    mutationFn: (email: string | null) => perfilService.updateEmail(email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: perfilKeys.all });
      toast.success('Email de notificaciones actualizado');
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo actualizar el email');
    },
  });
};

/**
 * Hook para marcar/desmarcar la API key como paga (toggle manual).
 * Habilita la corrección masiva global ("Corregir todo").
 */
export const useUpdateKeyPaga = () => {
  const queryClient = useQueryClient();

  return useMutation<{ message: string; gemini_api_key_paga: boolean }, Error, boolean>({
    mutationFn: (paga: boolean) => perfilService.updateKeyPaga(paga),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: perfilKeys.all });
      toast.success(
        res.gemini_api_key_paga
          ? 'API key marcada como paga. Ya podés usar "Corregir todo".'
          : 'API key marcada como gratuita.'
      );
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo actualizar la preferencia');
    },
  });
};
