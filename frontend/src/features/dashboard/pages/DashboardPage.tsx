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

import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/features/auth/hooks';
import { useProfile } from '@/features/perfil/hooks/usePerfil';
import { ROL } from '@/shared/types';
import { Spinner } from '@/shared/components/ui/Spinner';
import { Alert } from '@/shared/components/ui/Alert';
import { Button } from '@/shared/components/ui/Button';
import { DashboardAdmin } from '../components/DashboardAdmin';
import { DashboardCoordinador } from '../components/DashboardCoordinador';
import { DashboardTutor } from '../components/DashboardTutor';

export function DashboardPage() {
  const { user, isLoading } = useAuth();
  const { data: profile } = useProfile();
  const navigate = useNavigate();

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

  // Show API Key warning if not configured
  const showApiKeyWarning = profile && !profile.gemini_api_key_valid;

  // Render different dashboard based on role
  const renderDashboard = () => {
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
  };

  return (
    <div className="space-y-6">
      {/* API Key Warning */}
      {showApiKeyWarning && (
        <Alert variant="warning" title="⚠️ Configuración requerida">
          <p className="mb-3">
            Para utilizar las funciones de corrección automática, necesitas configurar tu API Key de Google Gemini.
          </p>
          <Button
            variant="primary"
            size="sm"
            onClick={() => navigate('/perfil')}
          >
            Ir a Configuración
          </Button>
        </Alert>
      )}

      {/* Dashboard Content */}
      {renderDashboard()}
    </div>
  );
}
