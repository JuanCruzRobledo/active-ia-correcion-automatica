/**
 * ComisionCard - Tutor comision card with quick stats.
 *
 * Displays comision info with pending entregas count and navigation button.
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md Section 4.1 - Dashboard Tutor
 */

import { useNavigate } from 'react-router-dom';
import { Button } from '@/shared/components/ui/Button';
import { ArrowRight, Users, Clock } from 'lucide-react';

interface Comision {
  id: number;
  nombre: string;
  comision: string;
  alumnos: number;
  pendientes: number;
}

interface ComisionCardProps {
  comision: Comision;
}

export function ComisionCard({ comision }: ComisionCardProps) {
  const navigate = useNavigate();

  const handleNavigate = () => {
    navigate(`/entregas?comision_id=${comision.id}`);
  };

  return (
    <div className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-accent/50">
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-foreground">{comision.nombre}</h3>
        <p className="text-sm text-muted-foreground">{comision.comision}</p>
      </div>

      <div className="mb-4 space-y-2">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Users className="h-4 w-4" />
          <span>{comision.alumnos} alumnos</span>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Clock className="h-4 w-4 text-warning" />
          <span className="font-medium text-foreground">
            {comision.pendientes} pendientes
          </span>
        </div>
      </div>

      <Button
        variant="outline"
        className="w-full"
        onClick={handleNavigate}
      >
        Ver entregas
        <ArrowRight className="ml-2 h-4 w-4" />
      </Button>
    </div>
  );
}
