import type { AnalisisArchivos } from '../types/politica';
import { LimiteNotaEntrega } from './LimiteNotaEntrega';

interface AnalisisArchivosEntregaProps {
  analisis?: AnalisisArchivos | null;
}

export function AnalisisArchivosEntrega({ analisis }: AnalisisArchivosEntregaProps) {
  if (!analisis) return null;

  return (
    <div className="space-y-3">
      <LimiteNotaEntrega limiteNota={analisis.limite_nota} rutas={analisis.rutas_penalizables} />
      {analisis.archivos_ignorados.length > 0 && (
        <details className="rounded-lg border border-border bg-muted/20 p-3">
          <summary className="cursor-pointer text-sm font-medium text-foreground">
            {analisis.limite_nota == null ? 'Archivos ignorados sin penalización' : 'Archivos ignorados'} ({analisis.archivos_ignorados.length})
          </summary>
          <ul className="mt-3 max-h-40 space-y-2 overflow-y-auto text-xs">
            {analisis.archivos_ignorados.map(({ ruta, motivo }) => (
              <li key={ruta} className="space-y-0.5">
                <p className="break-all font-mono text-foreground">{ruta}</p>
                <p className="text-muted-foreground">{motivo.replaceAll('_', ' ')}</p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
