import { Navigate } from 'react-router-dom';
import { useTenant } from '@/shared/context/useTenant';

interface SuperadminRouteProps {
  children: React.ReactNode;
}

/**
 * Guard de ruta para pantallas exclusivas de superadmin (ABM de universidades).
 * Un no-superadmin que navega directamente a la URL es redirigido a /dashboard
 * en vez de ver el panel — la entrada de menú ya está oculta (navConfig,
 * `roles: []`), pero la URL sigue siendo alcanzable a mano sin este guard.
 */
export const SuperadminRoute = ({ children }: SuperadminRouteProps) => {
  const { esSuperadmin } = useTenant();

  if (!esSuperadmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
};
