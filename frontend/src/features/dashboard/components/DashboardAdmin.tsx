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

import { useNavigate } from 'react-router-dom';
import { BookOpen, GraduationCap, Users, FileText, Plus } from 'lucide-react';
import { StatCard } from './StatCard';
import { QuickActions } from './QuickActions';
import { RecentActivity } from './RecentActivity';
import { useDashboardAdminStats, useActividadesRecientes } from '../hooks';
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';

export function DashboardAdmin() {
  const navigate = useNavigate();
  const { data: stats, isLoading, error } = useDashboardAdminStats();
  const { data: actividadesData, isLoading: actividadesLoading } = useActividadesRecientes({
    limit: 10,
  });

  // Loading state
  if (isLoading) {
    return <LoadingState title="Cargando tu panel…" />;
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
      onClick: () => navigate('/materias'),
    },
    {
      label: 'Crear Usuario',
      icon: Plus,
      onClick: () => navigate('/usuarios'),
    },
    {
      label: 'Crear Comisión',
      icon: Plus,
      onClick: () => navigate('/comisiones'),
    },
    {
      label: 'Crear Rúbrica',
      icon: Plus,
      onClick: () => navigate('/rubricas'),
    },
  ];

  // Map actividades to the format expected by RecentActivity component
  const recentActivities =
    actividadesData?.items.map((act) => ({
      id: act.id,
      text: act.descripcion,
      timestamp: act.created_at,
    })) ?? [];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2"><h1 className="text-2xl font-bold text-foreground">Dashboard Administrativo</h1><HelpButton title="Ayuda — Dashboard" content={helpContent.dashboard} /></div>
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
        <RecentActivity activities={recentActivities} isLoading={actividadesLoading} />
      </div>
    </div>
  );
}
