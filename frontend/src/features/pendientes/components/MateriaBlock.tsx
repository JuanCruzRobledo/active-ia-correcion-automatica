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
      <div className="flex w-full items-center justify-between px-5 py-4">
        <button
          onClick={() => setOpen((o) => !o)}
          className="flex items-center gap-3 text-left transition-opacity hover:opacity-80"
        >
          {open ? (
            <ChevronDown className="h-5 w-5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-5 w-5 text-muted-foreground" />
          )}
          <span className="text-base font-semibold text-foreground">{materia.nombre}</span>
        </button>
        <div className="flex items-center gap-2">
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
          {materia.totalEspera > 0 && (
            <ImportarButton
              scope="materia"
              materiaId={materia.id}
              label="Importar materia"
              modalTitle={`Importar — ${materia.nombre}`}
              size="sm"
            />
          )}
        </div>
      </div>

      {open && (
        <div className="space-y-3 border-t border-border px-5 py-4">
          {materia.unidades.map((u) => (
            <UnidadBlock key={u.id} unidad={u} showUrgentOnly={showUrgentOnly} />
          ))}
        </div>
      )}
    </div>
  );
}
