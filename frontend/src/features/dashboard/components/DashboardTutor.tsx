/**
 * DashboardTutor - Tutor dashboard with comisiones and pending/completed stats.
 *
 * Shows:
 * - 3 stat cards: Comisiones, Pendientes, Corregidas
 * - Mis Comisiones cards with details
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Tutor
 */

import { GraduationCap, Clock, CheckCircle, AlertTriangle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { StatCard } from './StatCard';
import { ComisionCard } from './ComisionCard';
import { CorregirTodoButton } from './CorregirTodoButton';
import { useDashboardTutorStats } from '../hooks';
import { usePendientesMoodle } from '@/features/pendientes';
import { Spinner } from '@/shared/components/ui';

export function DashboardTutor() {
  const { data: dashboardData, isLoading, error } = useDashboardTutorStats();
  const { data: pendientesData } = usePendientesMoodle();
  const navigate = useNavigate();

  const totalEsperaMoodle = pendientesData?.materias?.reduce(
    (acc, m) => acc + m.totalEspera,
    0
  ) ?? 0;

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
      {/* Banner Moodle pendientes */}
      {totalEsperaMoodle > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-warning/30 bg-warning/10 px-5 py-4">
          <div className="flex items-center gap-3">
            <AlertTriangle className="h-5 w-5 text-warning" />
            <p className="text-sm font-medium text-foreground">
              Tenés{' '}
              <span className="font-bold text-warning">{totalEsperaMoodle}</span>{' '}
              entrega{totalEsperaMoodle !== 1 ? 's' : ''} esperando corrección en Moodle.
            </p>
          </div>
          <button
            onClick={() => navigate('/pendientes')}
            className="rounded-md bg-warning px-4 py-2 text-sm font-medium text-warning-foreground hover:bg-warning/90"
          >
            Ver pendientes
          </button>
        </div>
      )}

      {/* Corrección masiva global (sólo API key paga) */}
      <CorregirTodoButton />

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
