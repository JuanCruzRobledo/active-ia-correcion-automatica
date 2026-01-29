/**
 * DashboardCoordinador - Coordinador dashboard with materia stats and correction progress.
 *
 * Shows:
 * - 3 stat cards: Comisiones, Rúbricas, Pendientes
 * - Estado de Correcciones por Comisión (progress bars)
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Coordinador
 */

import { GraduationCap, FileText, Clock } from 'lucide-react';
import { StatCard } from './StatCard';
import { CorrectionsProgress } from './CorrectionsProgress';
import { useDashboardCoordinadorStats } from '../hooks';
import { Spinner } from '@/shared/components/ui';

export function DashboardCoordinador() {
  const { data: dashboardData, isLoading, error } = useDashboardCoordinadorStats();

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
        <h1 className="text-2xl font-bold text-foreground">Dashboard - Mis Materias</h1>
        <p className="text-sm text-muted-foreground">
          Estado de correcciones y comisiones asignadas
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
          title="Rúbricas"
          value={dashboardData.rubricas}
          subtitle="activas"
          icon={FileText}
          variant="default"
        />
        <StatCard
          title="Pendientes"
          value={dashboardData.pendientes}
          subtitle="de corregir"
          icon={Clock}
          variant="warning"
        />
      </div>

      {/* Corrections Progress */}
      <CorrectionsProgress progress={dashboardData.corrections_progress} />
    </div>
  );
}
