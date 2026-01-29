/**
 * DashboardTutor - Tutor dashboard with comisiones and pending/completed stats.
 *
 * Shows:
 * - 3 stat cards: Comisiones, Pendientes, Corregidas
 * - Mis Comisiones cards with details
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Tutor
 */

import { GraduationCap, Clock, CheckCircle } from 'lucide-react';
import { StatCard } from './StatCard';
import { ComisionCard } from './ComisionCard';
import { useDashboardTutorStats } from '../hooks';
import { Spinner } from '@/shared/components/ui';

export function DashboardTutor() {
  const { data: dashboardData, isLoading, error } = useDashboardTutorStats();

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

  // No data state
  if (!dashboardData) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No hay datos disponibles</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">Dashboard - Mis Comisiones</h1>
        <p className="text-sm text-muted-foreground">
          Entregas pendientes y estado de correcciones
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-6 sm:grid-cols-3">
        <StatCard
          title="Comisiones"
          value={dashboardData.comisiones}
          subtitle="asignadas"
          icon={GraduationCap}
          variant="default"
        />
        <StatCard
          title="Pendientes"
          value={dashboardData.pendientes}
          subtitle="de corregir"
          icon={Clock}
          variant="warning"
        />
        <StatCard
          title="Corregidas"
          value={dashboardData.corregidas}
          subtitle="entregas"
          icon={CheckCircle}
          variant="success"
        />
      </div>

      {/* Comisiones Cards */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-foreground">Mis Comisiones</h2>
        <div className="grid gap-6 lg:grid-cols-2">
          {dashboardData.comisiones_details.map((comision) => (
            <ComisionCard key={comision.id} comision={comision} />
          ))}
        </div>
      </div>
    </div>
  );
}
