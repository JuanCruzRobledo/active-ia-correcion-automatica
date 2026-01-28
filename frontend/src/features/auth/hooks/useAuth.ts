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
import { getUser, isAuthenticated } from '../services/auth-service';
import type { UserInfo } from '@/shared/types';

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
