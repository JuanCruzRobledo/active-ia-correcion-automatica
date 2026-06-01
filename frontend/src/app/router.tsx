import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/shared/components/layout/AppLayout';
import { ProtectedRoute } from '@/shared/components/layout/ProtectedRoute';
import { PublicRoute } from '@/shared/components/layout/PublicRoute';
import { LoginPage, ChangePasswordPage } from '@/features/auth/pages';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { UsuariosPage } from '@/features/usuarios/pages/UsuariosPage';
import { MateriasPage } from '@/features/materias/pages/MateriasPage';
import { ComisionesPage } from '@/features/comisiones/pages/ComisionesPage';
import { RubricasPage } from '@/features/rubricas/pages/RubricasPage';
import { EntregasPage } from '@/features/entregas/pages/EntregasPage';
import { PendientesPage } from '@/features/pendientes/pages';
import { PorEntregarPage } from '@/features/por-entregar/pages';
import { PerfilPage } from '@/features/perfil/pages/PerfilPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <PublicRoute>
        <LoginPage />
      </PublicRoute>
    ),
  },
  {
    path: '/change-password',
    element: (
      <PublicRoute>
        <ChangePasswordPage />
      </PublicRoute>
    ),
  },
  {
    path: '/',
    element: (
      <ProtectedRoute>
        <AppLayout />
      </ProtectedRoute>
    ),
    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },
      {
        path: 'dashboard',
        element: <DashboardPage />,
      },
      // Admin routes
      {
        path: 'usuarios',
        element: <UsuariosPage />,
      },
      {
        path: 'materias',
        element: <MateriasPage />,
      },
      // Admin & Coordinador routes
      {
        path: 'comisiones',
        element: <ComisionesPage />,
      },
      {
        path: 'rubricas',
        element: <RubricasPage />,
      },
      // Tutor routes
      {
        path: 'entregas',
        element: <EntregasPage />,
      },
      {
        path: 'pendientes',
        element: <PendientesPage />,
      },
      {
        path: 'por-entregar',
        element: <PorEntregarPage />,
      },
      // Common routes
      {
        path: 'perfil',
        element: <PerfilPage />,
      },
    ],
  },
]);
