/**
 * DashboardAdmin - Admin dashboard with system-wide statistics.
 *
 * Shows:
 * - 4 stat cards: Materias, Comisiones, Usuarios, Rúbricas
 * - Quick actions section
 * - Recent activity section
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Admin
 */

import { BookOpen, GraduationCap, Users, FileText, Plus } from 'lucide-react';
import { StatCard } from './StatCard';
import { QuickActions } from './QuickActions';
import { RecentActivity } from './RecentActivity';
import { useDashboardAdminStats } from '../hooks';
import { Spinner } from '@/shared/components/ui';

export function DashboardAdmin() {
  const { data: stats, isLoading, error } = useDashboardAdminStats();

  // Loading state
  if (isLoading) {
    return (
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-destructive">Error al cargar estadísticas del dashboard</p>
        <p className="text-sm text-muted-foreground mt-2">
          {error instanceof Error ? error.message : 'Error desconocido'}
        </p>
      </div>
    );
  }

  // No data state (shouldn't happen but good to handle)
  if (!stats) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No hay datos disponibles</p>
      </div>
    );
  }

  const quickActions = [
    {
      label: 'Crear Materia',
      icon: Plus,
      onClick: () => {
        // TODO: Navigate to /admin/materias/nueva
        console.log('Crear Materia');
      },
    },
    {
      label: 'Crear Usuario',
      icon: Plus,
      onClick: () => {
        // TODO: Navigate to /admin/usuarios/nuevo
        console.log('Crear Usuario');
      },
    },
    {
      label: 'Crear Comisión',
      icon: Plus,
      onClick: () => {
        // TODO: Navigate to /admin/comisiones/nueva
        console.log('Crear Comisión');
      },
    },
  ];

  const recentActivities = [
    {
      id: 1,
      text: 'Usuario X creado',
      timestamp: '2026-01-28T10:30:00Z',
    },
    {
      id: 2,
      text: 'Materia Y actualizada',
      timestamp: '2026-01-28T09:15:00Z',
    },
    {
      id: 3,
      text: 'Rúbrica Z creada',
      timestamp: '2026-01-28T08:45:00Z',
    },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard Administrativo</h1>
        <p className="text-sm text-muted-foreground">
          Vista general del sistema Active-IA
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          title="Materias"
          value={stats.materias}
          subtitle="activas"
          icon={BookOpen}
          variant="default"
        />
        <StatCard
          title="Comisiones"
          value={stats.comisiones}
          subtitle="activas"
          icon={GraduationCap}
          variant="default"
        />
        <StatCard
          title="Usuarios"
          value={stats.usuarios}
          subtitle="activos"
          icon={Users}
          variant="default"
        />
        <StatCard
          title="Rúbricas"
          value={stats.rubricas}
          subtitle="activas"
          icon={FileText}
          variant="default"
        />
      </div>

      {/* Quick Actions & Recent Activity */}
      <div className="grid gap-6 lg:grid-cols-2">
        <QuickActions actions={quickActions} />
        <RecentActivity activities={recentActivities} />
      </div>
    </div>
  );
}
