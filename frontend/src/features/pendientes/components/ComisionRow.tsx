import { ExternalLink } from 'lucide-react';
import type { ComisionPendiente } from '../types';

interface ComisionRowProps {
  comision: ComisionPendiente;
}

export function ComisionRow({ comision }: ComisionRowProps) {
  return (
    <div className="flex items-center justify-between rounded-md border border-border bg-card px-4 py-3">
      <div className="flex items-center gap-3">
        <span className="text-sm font-medium text-foreground">{comision.nombre}</span>
        {comision.codigo && (
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {comision.codigo}
          </span>
        )}
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-3 text-sm">
          <span
            className={`font-semibold ${
              comision.espera > 0 ? 'text-destructive' : 'text-muted-foreground'
            }`}
          >
            {comision.espera} espera
          </span>
          <span className="text-success font-semibold">{comision.corregidos} corregidos</span>
          <span className="text-muted-foreground">{comision.sinEntrega} sin entrega</span>
        </div>

        {comision.moodleGraderUrl && comision.espera > 0 && (
          <a
            href={comision.moodleGraderUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            <ExternalLink className="h-3 w-3" />
            Ver en Moodle
          </a>
        )}
      </div>
    </div>
  );
}
