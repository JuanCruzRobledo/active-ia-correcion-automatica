import type { AlumnoGestion } from '../types';

interface Props {
  items: AlumnoGestion[];
  total: number;
}

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
          <div className="flex items-center justify-between bg-muted/40 px-4 py-2">
            <h3 className="font-semibold text-foreground">{regional}</h3>
            <span className="text-sm text-muted-foreground">
              {alumnos.length} alumno(s)
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-muted-foreground">
                  <th className="px-4 py-2 font-medium">Nombre</th>
                  <th className="px-4 py-2 font-medium">Apellido</th>
                  <th className="px-4 py-2 font-medium">Email</th>
                  <th className="px-4 py-2 font-medium">Comisión</th>
                  <th className="px-4 py-2 font-medium">Inactividad</th>
                  <th className="px-4 py-2 font-medium">Estatus</th>
                </tr>
              </thead>
              <tbody>
                {alumnos.map((a, i) => (
                  <tr key={`${a.email}-${i}`} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 text-foreground">{a.nombre}</td>
                    <td className="px-4 py-2 text-foreground">{a.apellido}</td>
                    <td className="px-4 py-2 text-muted-foreground">{a.email}</td>
                    <td className="px-4 py-2 text-foreground">{a.comision}</td>
                    <td className="px-4 py-2 text-foreground">{a.tiempo_inactividad}</td>
                    <td className="px-4 py-2">
                      <span
                        className={
                          a.suspendido
                            ? 'rounded-full bg-warning/10 px-2 py-0.5 text-xs text-warning'
                            : 'rounded-full bg-success/10 px-2 py-0.5 text-xs text-success'
                        }
                      >
                        {a.suspendido ? 'Inactivo' : 'Activo'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ))}
    </div>
  );
}
