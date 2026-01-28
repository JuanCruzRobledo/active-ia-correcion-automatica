/**
 * DashboardPage - Main dashboard that renders different views based on user role.
 *
 * Three different dashboard layouts:
 * - Admin: System-wide stats, quick actions, recent activity
 * - Coordinador: Comisiones stats, correction progress by comision
 * - Tutor: Mis comisiones cards, pending/completed stats
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1
 * Ref: skills/react-typescript/SKILL.md
 */

import { useAuth } from '@/features/auth/hooks';
import { ROL } from '@/shared/types';
import { Spinner } from '@/shared/components/ui/Spinner';
import { DashboardAdmin } from '../components/DashboardAdmin';
import { DashboardCoordinador } from '../components/DashboardCoordinador';
import { DashboardTutor } from '../components/DashboardTutor';

export function DashboardPage() {
  const { user, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">No se pudo cargar la información del usuario</p>
      </div>
    );
  }

  // Render different dashboard based on role
  switch (user.rol) {
    case ROL.ADMIN:
      return <DashboardAdmin />;
    case ROL.COORDINADOR:
      return <DashboardCoordinador />;
    case ROL.TUTOR:
      return <DashboardTutor />;
    default:
      return (
        <div className="flex h-[50vh] items-center justify-center">
          <p className="text-muted-foreground">Rol desconocido</p>
        </div>
      );
  }
}
