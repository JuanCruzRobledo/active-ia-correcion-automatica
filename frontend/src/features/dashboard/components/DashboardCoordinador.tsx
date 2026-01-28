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

export function DashboardCoordinador() {
  // TODO: Fetch real stats from API
  const stats = {
    comisiones: 17,
    rubricas: 12,
    pendientes: 145,
  };

  const correctionsProgress = [
    {
      id: 1,
      comision: 'Prog1 - Comisión A',
      tutor: 'Carlos',
      completed: 28,
      total: 35,
      lastActivity: '2026-01-28T12:30:00Z',
    },
    {
      id: 2,
      comision: 'Prog1 - Comisión B',
      tutor: 'Ana',
      completed: 30,
      total: 30,
      lastActivity: '2026-01-27T18:00:00Z',
    },
    {
      id: 3,
      comision: 'Prog2 - Comisión A',
      tutor: 'Luis',
      completed: 12,
      total: 32,
      lastActivity: '2026-01-28T10:15:00Z',
    },
  ];

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
          value={stats.comisiones}
          subtitle="asignadas"
          icon={GraduationCap}
          variant="default"
        />
        <StatCard
          title="Rúbricas"
          value={stats.rubricas}
          subtitle="activas"
          icon={FileText}
          variant="default"
        />
        <StatCard
          title="Pendientes"
          value={stats.pendientes}
          subtitle="de corregir"
          icon={Clock}
          variant="warning"
        />
      </div>

      {/* Corrections Progress */}
      <CorrectionsProgress progress={correctionsProgress} />
    </div>
  );
}
