import { AlertTriangle } from 'lucide-react';

interface LimiteNotaEntregaProps {
  limiteNota?: number | null;
  rutas?: string[];
}

/** Explica una restricción ya determinada por el backend, sin recalcular notas. */
export function LimiteNotaEntrega({ limiteNota, rutas = [] }: LimiteNotaEntregaProps) {
  if (limiteNota == null) return null;

  return (
    <section className="rounded-lg border border-warning/30 bg-warning/10 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warning" aria-hidden="true" />
        <div className="min-w-0 space-y-2 text-sm">
          <h4 className="font-semibold text-foreground">Límite de nota por archivos no evaluables</h4>
          <p className="font-medium text-foreground">Máximo {limiteNota}/100</p>
          <p className="text-muted-foreground">
            El límite se aplica después de evaluar el código y nunca aumenta la nota obtenida.
          </p>
          {rutas.length > 0 && (
            <ul className="max-h-32 space-y-1 overflow-y-auto font-mono text-xs text-foreground">
              {rutas.map((ruta) => <li key={ruta} className="break-all">{ruta}</li>)}
            </ul>
          )}
          <p className="text-muted-foreground">
            Presentá una nueva entrega sin estos archivos para que se evalúe nuevamente sin esta restricción.
          </p>
        </div>
      </div>
    </section>
  );
}
