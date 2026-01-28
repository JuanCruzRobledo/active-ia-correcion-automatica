import { createBrowserRouter, Navigate } from 'react-router-dom';
import { AppLayout } from '@/shared/components/layout/AppLayout';
import { LoginPage } from '@/features/auth/pages/LoginPage';
import { DashboardPage } from '@/features/dashboard/pages/DashboardPage';
import { UsuariosPage } from '@/features/usuarios/pages/UsuariosPage';
import { MateriasPage } from '@/features/materias/pages/MateriasPage';
import { ComisionesPage } from '@/features/comisiones/pages/ComisionesPage';
import { RubricasPage } from '@/features/rubricas/pages/RubricasPage';
import { EntregasPage } from '@/features/entregas/pages/EntregasPage';
import { CorreccionesPage } from '@/features/correcciones/pages/CorreccionesPage';
import { PerfilPage } from '@/features/perfil/pages/PerfilPage';

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginPage />,
  },
  {
    path: '/',
    element: <AppLayout />,
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
        path: 'correcciones',
        element: <CorreccionesPage />,
      },
      // Common routes
      {
        path: 'perfil',
        element: <PerfilPage />,
      },
    ],
  },
]);
