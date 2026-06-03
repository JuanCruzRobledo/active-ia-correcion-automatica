import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { LoadingState } from '@/shared/components/ui';
import { AppLayout } from '@/shared/components/layout/AppLayout';
import { ProtectedRoute } from '@/shared/components/layout/ProtectedRoute';
import { PublicRoute } from '@/shared/components/layout/PublicRoute';
import { LoginPage, ChangePasswordPage } from '@/features/auth/pages';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { UsuariosPage } from '@/features/usuarios/pages/UsuariosPage';
import { MateriasPage } from '@/features/materias/pages/MateriasPage';
import { CohortesPage } from '@/features/cohortes/pages';
import { MateriaDashboardConfigPage } from '@/features/materia-dashboard/pages';
import { CronConfigPage } from '@/features/cron-config/pages';
import { ComisionesPage } from '@/features/comisiones/pages/ComisionesPage';
import { RubricasPage } from '@/features/rubricas/pages/RubricasPage';
import { EntregasPage } from '@/features/entregas/pages/EntregasPage';
import { PendientesPage } from '@/features/pendientes/pages';
import { PorEntregarPage } from '@/features/por-entregar/pages';
import { GestionPage } from '@/features/gestion/pages';
import { PerfilPage } from '@/features/perfil/pages/PerfilPage';

// Lazy: el dashboard de gestores trae Recharts (~350 KB gzip). Se carga solo al
// entrar a /avance, así no pesa en el bundle principal del resto de la app.
const DashboardGestorPage = lazy(() =>
  import('@/features/dashboard-gestor/pages').then((m) => ({
    default: m.DashboardGestorPage,
  }))
);

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
      {
        path: 'cohortes',
        element: <CohortesPage />,
      },
      {
        path: 'materias/:materiaId/dashboard',
        element: <MateriaDashboardConfigPage />,
      },
      {
        path: 'snapshots',
        element: <CronConfigPage />,
      },
      {
        path: 'avance',
        element: (
          <Suspense fallback={<LoadingState title="Cargando dashboard…" />}>
            <DashboardGestorPage />
          </Suspense>
        ),
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
      // Gestor routes
      {
        path: 'gestion',
        element: <GestionPage />,
      },
      // Common routes
      {
        path: 'perfil',
        element: <PerfilPage />,
      },
    ],
  },
]);
