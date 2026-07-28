import { lazy } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/shared/components/layout/AppLayout';
import { ProtectedRoute } from '@/shared/components/layout/ProtectedRoute';
import { PublicRoute } from '@/shared/components/layout/PublicRoute';
import { SuperadminRoute } from '@/shared/components/layout/SuperadminRoute';
// Auth: eager. Son la puerta de entrada (fuera del AppLayout) y no conviene
// meter un round-trip de Suspense en el camino crítico del login.
import { LoginPage, ChangePasswordPage } from '@/features/auth/pages';

// PERF-014: el resto de las páginas se cargan lazy (route-level code-splitting).
// El bundle inicial ya no arrastra pantallas de admin/gestor que la mayoría de
// los roles no visita. El <Suspense> que las envuelve vive en AppLayout (Outlet).
// Todas exportan de forma nombrada → mapeamos a `default` para React.lazy.
const DashboardPage = lazy(() =>
  import('@/features/dashboard/pages/DashboardPage').then((m) => ({ default: m.DashboardPage }))
);
const UsuariosPage = lazy(() =>
  import('@/features/usuarios/pages/UsuariosPage').then((m) => ({ default: m.UsuariosPage }))
);
const MateriasPage = lazy(() =>
  import('@/features/materias/pages/MateriasPage').then((m) => ({ default: m.MateriasPage }))
);
const CohortesPage = lazy(() =>
  import('@/features/cohortes/pages').then((m) => ({ default: m.CohortesPage }))
);
const TutoresNexoPage = lazy(() =>
  import('@/features/tutores-nexo/pages').then((m) => ({ default: m.TutoresNexoPage }))
);
const NotificacionesPage = lazy(() =>
  import('@/features/notificaciones/pages').then((m) => ({ default: m.NotificacionesPage }))
);
const MateriaDashboardConfigPage = lazy(() =>
  import('@/features/materia-dashboard/pages').then((m) => ({
    default: m.MateriaDashboardConfigPage,
  }))
);
const CronConfigPage = lazy(() =>
  import('@/features/cron-config/pages').then((m) => ({ default: m.CronConfigPage }))
);
const ComisionesPage = lazy(() =>
  import('@/features/comisiones/pages/ComisionesPage').then((m) => ({ default: m.ComisionesPage }))
);
const RubricasPage = lazy(() =>
  import('@/features/rubricas/pages/RubricasPage').then((m) => ({ default: m.RubricasPage }))
);
const EntregasPage = lazy(() =>
  import('@/features/entregas/pages/EntregasPage').then((m) => ({ default: m.EntregasPage }))
);
const PendientesPage = lazy(() =>
  import('@/features/pendientes/pages').then((m) => ({ default: m.PendientesPage }))
);
const PorEntregarPage = lazy(() =>
  import('@/features/por-entregar/pages').then((m) => ({ default: m.PorEntregarPage }))
);
const GestionPage = lazy(() =>
  import('@/features/gestion/pages').then((m) => ({ default: m.GestionPage }))
);
const PerfilPage = lazy(() =>
  import('@/features/perfil/pages/PerfilPage').then((m) => ({ default: m.PerfilPage }))
);
const CierreCursadaPage = lazy(() =>
  import('@/features/cierre-cursada/pages').then((m) => ({ default: m.CierreCursadaPage }))
);
// El dashboard de gestores trae Recharts (~350 KB gzip); lazy desde siempre.
const DashboardGestorPage = lazy(() =>
  import('@/features/dashboard-gestor/pages').then((m) => ({
    default: m.DashboardGestorPage,
  }))
);
const UniversidadesPage = lazy(() =>
  import('@/features/universidades/pages').then((m) => ({ default: m.UniversidadesPage }))
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
      // Fase 5 multi-tenant: ABM de universidades, sólo superadmin.
      {
        path: 'universidades',
        element: (
          <SuperadminRoute>
            <UniversidadesPage />
          </SuperadminRoute>
        ),
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
        path: 'tutores-nexo',
        element: <TutoresNexoPage />,
      },
      {
        path: 'notificaciones',
        element: <NotificacionesPage />,
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
        element: <DashboardGestorPage />,
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
      {
        path: 'cierre-cursada',
        element: <CierreCursadaPage />,
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
