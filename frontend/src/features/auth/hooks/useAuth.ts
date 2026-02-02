/**
 * useAuth Hook
 *
 * Provides access to current authentication state and user info.
 * This is a simple hook that reads from localStorage.
 * For a reactive version with context, use AuthProvider (if implemented).
 *
 * Ref: skills/react-typescript/SKILL.md
 */

import { useState, useEffect } from 'react';
import { useMutation } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { getUser, isAuthenticated, changePassword } from '../services/auth-service';
import type { UserInfo, ChangePasswordRequest } from '@/shared/types';

interface UseAuthReturn {
  /**
   * Current authenticated user or null if not authenticated
   */
  user: UserInfo | null;

  /**
   * Whether the user is currently authenticated
   */
  isAuthenticated: boolean;

  /**
   * Whether the auth state is being initialized
   */
  isLoading: boolean;
}

/**
 * Hook to access current authentication state.
 *
 * @returns Authentication state with user info
 *
 * @example
 * ```tsx
 * function MyComponent() {
 *   const { user, isAuthenticated, isLoading } = useAuth();
 *
 *   if (isLoading) return <Spinner />;
 *   if (!isAuthenticated) return <Redirect to="/login" />;
 *
 *   return <div>Welcome, {user.nombre}</div>;
 * }
 * ```
 */
export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check authentication status on mount
    const checkAuth = () => {
      const authStatus = isAuthenticated();
      setAuthenticated(authStatus);

      if (authStatus) {
        const userData = getUser();
        setUser(userData);
      } else {
        setUser(null);
      }

      setIsLoading(false);
    };

    checkAuth();

    // Listen for storage changes (for multi-tab sync)
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'auth_token' || e.key === 'auth_user') {
        checkAuth();
      }
    };

    window.addEventListener('storage', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return {
    user,
    isAuthenticated: authenticated,
    isLoading,
  };
}

/**
 * Hook to change user password.
 *
 * @returns Mutation hook for password change
 *
 * @example
 * ```tsx
 * function ChangePasswordForm() {
 *   const changePasswordMutation = useChangePassword();
 *
 *   const handleSubmit = () => {
 *     changePasswordMutation.mutate({
 *       currentPassword: 'oldpass',
 *       newPassword: 'newpass',
 *     });
 *   };
 * }
 * ```
 */
export function useChangePassword() {
  return useMutation({
    mutationFn: (data: ChangePasswordRequest) => changePassword(data),
    onSuccess: () => {
      toast.success('Contraseña actualizada exitosamente');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Error al cambiar contraseña');
    },
  });
}
