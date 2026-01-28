/**
 * useLogout Hook
 *
 * Provides mutation for user logout.
 * Clears authentication data and redirects to login.
 *
 * Ref: skills/react-typescript/SKILL.md
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-AUTH-03
 */

import { useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { logout } from '../services/auth-service';

/**
 * Hook for user logout.
 *
 * @returns React Query mutation object
 *
 * @example
 * ```tsx
 * function LogoutButton() {
 *   const logoutMutation = useLogout();
 *
 *   return (
 *     <Button
 *       variant="ghost"
 *       onClick={() => logoutMutation.mutate()}
 *       disabled={logoutMutation.isPending}
 *     >
 *       Cerrar sesión
 *     </Button>
 *   );
 * }
 * ```
 */
export function useLogout() {
  return useMutation<void, Error, void>({
    mutationFn: async () => {
      // logout() handles clearing storage and redirect
      logout();
    },

    onSuccess: () => {
      toast.success('Sesión cerrada correctamente');
    },

    onError: (error) => {
      console.error('[Logout Error]', error);
      // Even if there's an error, we should still clear local data
      logout();
    },
  });
}
