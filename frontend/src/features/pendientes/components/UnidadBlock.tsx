import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { UnidadPendiente } from '../types';
import { ComisionRow } from './ComisionRow';

interface UnidadBlockProps {
  unidad: UnidadPendiente;
  showUrgentOnly: boolean;
}

export function UnidadBlock({ unidad, showUrgentOnly }: UnidadBlockProps) {
  const [open, setOpen] = useState(true);

  const comisiones = showUrgentOnly
    ? unidad.comisiones.filter((c) => c.espera > 0)
    : unidad.comisiones;

  if (showUrgentOnly && comisiones.length === 0) return null;

  return (
    <div className="rounded-md border border-border">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-muted/50"
      >
        <div className="flex items-center gap-3">
          {open ? (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
          <div>
            <span className="text-sm font-medium text-foreground">{unidad.titulo}</span>
            <span className="ml-2 text-xs text-muted-foreground">{unidad.subtitulo}</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {unidad.espera > 0 && (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-medium text-destructive">
              {unidad.espera} pendientes
            </span>
          )}
          <span className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground">
            {unidad.corregidos} ok
          </span>
        </div>
      </button>

      {open && (
        <div className="space-y-2 border-t border-border px-4 py-3">
          {comisiones.map((c) => (
            <ComisionRow key={c.id} comision={c} />
          ))}
        </div>
      )}
    </div>
  );
}
