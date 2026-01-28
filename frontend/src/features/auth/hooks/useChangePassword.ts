/**
 * useChangePassword Hook
 *
 * React Query mutation for changing user password.
 * Handles first login password change with proper navigation.
 *
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-AUTH-02
 */

import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import * as authService from '../services/auth-service';
import type { ChangePasswordRequest } from '@/shared/types';

export function useChangePassword() {
  const navigate = useNavigate();

  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => authService.changePassword(data),

    onSuccess: () => {
      // Get current user from localStorage
      const user = authService.getUser();

      if (user) {
        // Update primer_login flag in localStorage
        const updatedUser = {
          ...user,
          primer_login: false,
        };
        authService.updateStoredUser(updatedUser);
      }

      // Show success toast
      toast.success('Contraseña cambiada exitosamente');

      // Navigate to dashboard
      navigate('/dashboard');
    },

    onError: (error: Error) => {
      // Show error toast
      toast.error(error.message || 'Error al cambiar la contraseña');
    },
  });
}
