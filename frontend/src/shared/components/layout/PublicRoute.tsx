import { Navigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/hooks';
import { Spinner } from '../ui/Spinner';

interface PublicRouteProps {
  children: React.ReactNode;
}

/**
 * PublicRoute component for routes that should only be accessible when NOT authenticated.
 * If user is already authenticated, redirects to dashboard.
 *
 * @example
 * ```tsx
 * <PublicRoute>
 *   <LoginPage />
 * </PublicRoute>
 * ```
 */
export const PublicRoute = ({ children }: PublicRouteProps) => {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Spinner size="lg" label="Cargando..." />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
