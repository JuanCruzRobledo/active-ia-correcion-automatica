import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import type { MateriaPendiente } from '../types';
import { UnidadBlock } from './UnidadBlock';
import { ImportarButton } from './ImportarButton';

interface MateriaBlockProps {
  materia: MateriaPendiente;
  showUrgentOnly: boolean;
}

export function MateriaBlock({ materia, showUrgentOnly }: MateriaBlockProps) {
  const [open, setOpen] = useState(true);

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex w-full flex-col gap-2 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex min-h-11 min-w-0 items-center gap-3 text-left transition-opacity hover:opacity-80"
        >
          {open ? (
            <ChevronDown className="h-5 w-5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-5 w-5 shrink-0 text-muted-foreground" />
          )}
          <span className="truncate text-base font-semibold text-foreground">{materia.nombre}</span>
        </button>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="flex flex-wrap items-center gap-2">
            {materia.totalEspera > 0 && (
              <span className="rounded-full bg-destructive/10 px-3 py-1 text-xs font-semibold text-destructive">
                {materia.totalEspera} pendientes
              </span>
            )}
            <span className="rounded-full bg-success/10 px-3 py-1 text-xs font-semibold text-success">
              {materia.totalCorregidos} corregidos
            </span>
            <span className="rounded-full bg-muted px-3 py-1 text-xs text-muted-foreground">
              {materia.totalSinEntrega} sin entrega
            </span>
          </div>
          {materia.totalEspera > 0 && (
            <ImportarButton
              scope="materia"
              materiaId={materia.id}
              label="Importar materia"
              modalTitle={`Importar — ${materia.nombre}`}
              size="sm"
              fullWidth
            />
          )}
        </div>
      </div>

      {open && (
        <div className="space-y-3 border-t border-border px-4 py-4 sm:px-5">
          {materia.unidades.map((u) => (
            <UnidadBlock key={u.id} unidad={u} showUrgentOnly={showUrgentOnly} />
          ))}
        </div>
      )}
    </div>
  );
}
