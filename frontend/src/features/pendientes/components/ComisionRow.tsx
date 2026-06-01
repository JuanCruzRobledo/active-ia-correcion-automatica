import { ExternalLink, FileText } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { ComisionPendiente } from '../types';
import { ImportarButton } from './ImportarButton';

interface ComisionRowProps {
  comision: ComisionPendiente;
  rubricaId: number;
}

export function ComisionRow({ comision, rubricaId }: ComisionRowProps) {
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

        {comision.espera > 0 && (
          <ImportarButton
            scope="comision_unidad"
            rubricaId={rubricaId}
            comisionId={comision.id}
            label="Importar"
            modalTitle={`Importar — ${comision.nombre}`}
            size="sm"
          />
        )}

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

        <Link
          to={`/entregas?comision_id=${comision.id}&rubrica_id=${rubricaId}`}
          className="flex items-center gap-1 rounded-md border border-border bg-background px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-muted"
        >
          <FileText className="h-3 w-3" />
          Ver entregas
        </Link>
      </div>
    </div>
  );
}
