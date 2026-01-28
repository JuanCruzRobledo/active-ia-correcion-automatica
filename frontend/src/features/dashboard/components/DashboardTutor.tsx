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

export function DashboardTutor() {
  // TODO: Fetch real stats from API
  const stats = {
    comisiones: 2,
    pendientes: 28,
    corregidas: 156,
  };

  const comisiones = [
    {
      id: 1,
      nombre: 'Programación 1',
      comision: 'Comisión A - 2026',
      alumnos: 35,
      pendientes: 12,
    },
    {
      id: 2,
      nombre: 'Programación 2',
      comision: 'Comisión B - 2026',
      alumnos: 32,
      pendientes: 16,
    },
  ];

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
          value={stats.comisiones}
          subtitle="asignadas"
          icon={GraduationCap}
          variant="default"
        />
        <StatCard
          title="Pendientes"
          value={stats.pendientes}
          subtitle="de corregir"
          icon={Clock}
          variant="warning"
        />
        <StatCard
          title="Corregidas"
          value={stats.corregidas}
          subtitle="entregas"
          icon={CheckCircle}
          variant="success"
        />
      </div>

      {/* Comisiones Cards */}
      <div>
        <h2 className="mb-4 text-lg font-semibold text-foreground">Mis Comisiones</h2>
        <div className="grid gap-6 lg:grid-cols-2">
          {comisiones.map((comision) => (
            <ComisionCard key={comision.id} comision={comision} />
          ))}
        </div>
      </div>
    </div>
  );
}
