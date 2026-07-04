import { useState } from 'react';
import { Download } from 'lucide-react';
import toast from 'react-hot-toast';
import { Button, EmptyState } from '@/shared/components/ui';
import { cierreCursadaService } from '../services/cierre-cursada.service';
import type { CierreRun } from '../types';

interface Props {
  runs: CierreRun[];
}

/** Corridas pasadas de cierre de cursada de una materia, con descarga del Excel. */
export const HistorialRunsTable = ({ runs }: Props) => {
  const [descargando, setDescargando] = useState<number | null>(null);

  const descargar = async (runId: number) => {
    setDescargando(runId);
    try {
      await cierreCursadaService.descargarExcel(runId);
    } catch {
      toast.error('No se pudo descargar el Excel');
    } finally {
      setDescargando(null);
    }
  };

  if (runs.length === 0) {
    return <EmptyState title="Sin corridas todavía" description="Generá el primer cierre de cursada de esta materia." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border text-left text-muted-foreground">
            <th className="py-2 pr-2">Generado</th>
            <th className="py-2 pr-2">Umbral TP</th>
            <th className="py-2 pr-2">Promociona</th>
            <th className="py-2 pr-2">Regulariza</th>
            <th className="py-2 pr-2">Recursa</th>
            <th className="py-2 pr-2">Total</th>
            <th className="py-2 pr-2" />
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} className="border-b border-border/60">
              <td className="py-2 pr-2">{new Date(r.created_at).toLocaleString('es-AR')}</td>
              <td className="py-2 pr-2">{r.umbral_tp_pct}%</td>
              <td className="py-2 pr-2">{r.total_promociona}</td>
              <td className="py-2 pr-2">{r.total_regulariza}</td>
              <td className="py-2 pr-2">{r.total_recursa}</td>
              <td className="py-2 pr-2">{r.total_alumnos}</td>
              <td className="py-2 pr-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => descargar(r.id)}
                  isLoading={descargando === r.id}
                >
                  <Download className="mr-1 h-4 w-4" />
                  Excel
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
