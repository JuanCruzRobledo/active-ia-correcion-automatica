import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Send, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { Modal } from '@/shared/components/ui/Modal';
import { entregarTodoStream } from '../services/por-entregar.service';
import { POR_ENTREGAR_QUERY_KEY } from '../hooks/usePorEntregar';
import type { EntregaMasivaResumen } from '../types';

interface EntregarTodoButtonProps {
  /** Cantidad de correcciones automáticas (TP) que se subirán en bloque. */
  totalAutomaticas: number;
}

type Fase = 'idle' | 'streaming' | 'done' | 'error';

export function EntregarTodoButton({ totalAutomaticas }: EntregarTodoButtonProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [fase, setFase] = useState<Fase>('idle');
  const [progreso, setProgreso] = useState<{ procesadas: number; total: number } | null>(null);
  const [resumen, setResumen] = useState<EntregaMasivaResumen | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleClick = () => {
    setOpen(true);
    setFase('streaming');
    setProgreso(null);
    setResumen(null);
    setErrorMsg(null);

    void entregarTodoStream({
      onTotal: (total) => setProgreso({ procesadas: 0, total }),
      onProgreso: (procesadas, total) => setProgreso({ procesadas, total }),
      onResumen: (r) => {
        setResumen(r);
        setFase('done');
        queryClient.invalidateQueries({ queryKey: POR_ENTREGAR_QUERY_KEY });
        queryClient.invalidateQueries({ queryKey: ['entregas'] });
      },
      onError: (msg) => {
        setErrorMsg(msg);
        setFase('error');
      },
    });
  };

  const handleClose = () => {
    setOpen(false);
    setFase('idle');
    setProgreso(null);
    setResumen(null);
    setErrorMsg(null);
  };

  const pct =
    progreso && progreso.total > 0
      ? Math.round((progreso.procesadas / progreso.total) * 100)
      : 0;

  return (
    <>
      <button
        onClick={handleClick}
        disabled={(open && fase === 'streaming') || totalAutomaticas === 0}
        className="flex flex-1 cursor-pointer items-center justify-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50 touch-manipulation min-h-[44px] sm:flex-none"
      >
        <Send className="h-4 w-4 shrink-0" />
        Entregar todo ({totalAutomaticas})
      </button>

      <Modal
        isOpen={open}
        onClose={handleClose}
        title="Entregar todo a Moodle"
        size="lg"
        footer={
          <button
            onClick={handleClose}
            disabled={fase === 'streaming'}
            className="cursor-pointer rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
          >
            {fase === 'done' || fase === 'error' ? 'Cerrar' : 'Cancelar'}
          </button>
        }
      >
        {fase === 'streaming' && (
          <div className="space-y-3 py-6">
            {progreso ? (
              <>
                <p className="text-center text-sm text-muted-foreground">
                  Publicando notas y feedback en Moodle…
                </p>
                <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-center text-sm font-medium text-foreground">
                  Subiendo {progreso.procesadas} de {progreso.total}  ({pct}%)
                </p>
              </>
            ) : (
              <p className="text-center text-sm text-muted-foreground">Conectando…</p>
            )}
          </div>
        )}

        {fase === 'error' && (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <AlertCircle className="h-10 w-10 text-destructive" />
            <p className="font-semibold text-foreground">No se pudo entregar</p>
            <p className="text-sm text-muted-foreground">{errorMsg}</p>
          </div>
        )}

        {fase === 'done' && resumen && <ResumenView data={resumen} />}
      </Modal>
    </>
  );
}

function ResumenView({ data }: { data: EntregaMasivaResumen }) {
  const [showErrores, setShowErrores] = useState(false);

  const chips: { label: string; value: number; className: string }[] = [
    { label: 'Enviadas', value: data.enviadas, className: 'bg-success/10 text-success' },
    { label: 'Ya enviadas', value: data.ya_enviadas, className: 'bg-muted text-muted-foreground' },
    {
      label: 'Ya estaban en Moodle',
      value: data.ya_calificadas_en_moodle,
      className: 'bg-muted text-muted-foreground',
    },
    {
      label: 'Re-entregas re-subidas',
      value: data.reenviadas_reentrega ?? 0,
      className: 'bg-primary/10 text-primary',
    },
    {
      label: 'Requieren comentario',
      value: data.omitidas_requieren_comentario,
      className: 'bg-warning/10 text-warning',
    },
    { label: 'Errores', value: data.errores.length, className: 'bg-destructive/10 text-destructive' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <CheckCircle className="h-6 w-6 text-success" />
        <p className="font-semibold text-foreground">
          {data.enviadas > 0
            ? `Se entregaron ${data.enviadas} corrección(es) a Moodle`
            : 'No se entregó ninguna corrección nueva'}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {chips.map((c) => (
          <div key={c.label} className={`rounded-md px-3 py-2 text-center ${c.className}`}>
            <div className="text-lg font-bold">{c.value}</div>
            <div className="text-xs">{c.label}</div>
          </div>
        ))}
      </div>

      {data.ya_calificadas_en_moodle > 0 && (
        <p className="rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          {data.ya_calificadas_en_moodle} corrección(es) ya tenían nota en Moodle (calificadas por
          fuera de Active-IA). No se reenviaron y se quitaron de la lista.
        </p>
      )}

      {(data.reenviadas_reentrega ?? 0) > 0 && (
        <p className="rounded-md bg-primary/10 px-3 py-2 text-xs text-primary">
          {data.reenviadas_reentrega} re-entrega(s): el alumno volvió a entregar después de la nota,
          así que se subió la nota nueva pisando la anterior.
        </p>
      )}

      {data.omitidas_requieren_comentario > 0 && (
        <p className="rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
          {data.omitidas_requieren_comentario} corrección(es) requieren que escribas un comentario
          (no son TP). Subilas a mano con el botón “Subir” de cada fila.
        </p>
      )}

      {data.errores.length > 0 && (
        <div className="rounded-md border border-border">
          <button
            onClick={() => setShowErrores((s) => !s)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm font-medium text-destructive"
          >
            {showErrores ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
            {data.errores.length} con error
          </button>
          {showErrores && (
            <ul className="max-h-40 space-y-1 overflow-y-auto border-t border-border px-3 py-2 text-xs">
              {data.errores.map((e, i) => (
                <li key={i} className="text-muted-foreground">
                  <span className="font-medium text-foreground">{e.alumno}</span>: {e.motivo}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
