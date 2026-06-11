import { ResponsiveTable, type TableColumn } from '@/shared/components/ui';
import type { AlumnoGestion } from '../types';

interface Props {
  items: AlumnoGestion[];
  total: number;
}

function EstatusBadge({ suspendido }: { suspendido: boolean }) {
  return (
    <span
      className={
        suspendido
          ? 'rounded-full bg-warning/10 px-2 py-0.5 text-xs text-warning'
          : 'rounded-full bg-success/10 px-2 py-0.5 text-xs text-success'
      }
    >
      {suspendido ? 'Inactivo' : 'Activo'}
    </span>
  );
}

const COLUMNS: TableColumn<AlumnoGestion>[] = [
  { key: 'nombre', header: 'Nombre', render: (a) => a.nombre },
  { key: 'apellido', header: 'Apellido', render: (a) => a.apellido },
  {
    key: 'email',
    header: 'Email',
    render: (a) => <span className="break-all text-muted-foreground">{a.email}</span>,
  },
  { key: 'comision', header: 'Comisión', render: (a) => a.comision },
  { key: 'inactividad', header: 'Inactividad', render: (a) => a.tiempo_inactividad },
  {
    key: 'estatus',
    header: 'Estatus',
    render: (a) => <EstatusBadge suspendido={a.suspendido} />,
  },
];

export function ResultadosGestionTable({ items, total }: Props) {
  // Agrupar por regional (los items ya vienen ordenados por regional→comisión).
  const grupos = new Map<string, AlumnoGestion[]>();
  for (const a of items) {
    const arr = grupos.get(a.regional) ?? [];
    arr.push(a);
    grupos.set(a.regional, arr);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <span className="rounded-full bg-accent/10 px-3 py-1 font-medium text-accent">
          {total} alumno(s) con estos filtros
        </span>
      </div>

      {[...grupos.entries()].map(([regional, alumnos]) => (
        <div key={regional} className="overflow-hidden rounded-lg border border-border">
          <div className="flex items-center justify-between gap-2 bg-muted/40 px-4 py-2">
            <h3 className="min-w-0 break-words font-semibold text-foreground">{regional}</h3>
            <span className="shrink-0 text-sm text-muted-foreground">
              {alumnos.length} alumno(s)
            </span>
          </div>
          {/* En lg: tabla clásica (look idéntico); en mobile: cards apiladas. */}
          <div className="p-3 lg:p-0">
            <ResponsiveTable
              columns={COLUMNS}
              data={alumnos}
              keyExtractor={(a) => `${a.email}-${a.comision}-${a.tiempo_inactividad}`}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
