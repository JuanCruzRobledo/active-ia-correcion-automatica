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
import { HelpButton, LoadingState } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';

export function DashboardCoordinador() {
  const { data: dashboardData, isLoading, error } = useDashboardCoordinadorStats();

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

  // No data state
  if (!dashboardData) {
    return (
      <div className="text-center py-12">
        <p className="text-muted-foreground">No hay datos disponibles</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* Header */}
      <div>
        <div className="flex flex-wrap items-center gap-2"><h1 className="text-xl font-bold text-foreground sm:text-2xl">Dashboard - Mis Materias</h1><HelpButton title="Ayuda — Dashboard" content={helpContent.dashboard} /></div>
        <p className="text-sm text-muted-foreground">
          Estado de correcciones y comisiones asignadas
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:gap-6 grid-cols-1 sm:grid-cols-3">
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
