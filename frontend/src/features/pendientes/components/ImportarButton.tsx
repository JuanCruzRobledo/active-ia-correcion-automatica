import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { DownloadCloud, CheckCircle, AlertCircle, ChevronDown, ChevronRight } from 'lucide-react';
import { Modal } from '@/shared/components/ui/Modal';
import { importarMoodleStream } from '../services/pendientes.service';
import { PENDIENTES_QUERY_KEY } from '../hooks/usePendientesMoodle';
import type { ImportScope, ImportarMoodleResponse } from '../types';

interface ImportarButtonProps {
  scope: ImportScope;
  rubricaId?: number;
  comisionId?: number;
  materiaId?: number;
  label: string;
  modalTitle: string;
  size?: 'sm' | 'md';
}

type Fase = 'idle' | 'streaming' | 'done' | 'error';

export function ImportarButton({
  scope,
  rubricaId,
  comisionId,
  materiaId,
  label,
  modalTitle,
  size = 'md',
}: ImportarButtonProps) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [fase, setFase] = useState<Fase>('idle');
  const [prep, setPrep] = useState<{ listos: number; total: number } | null>(null);
  const [progreso, setProgreso] = useState<{ procesadas: number; total: number } | null>(null);
  const [resumen, setResumen] = useState<ImportarMoodleResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleClick = () => {
    setOpen(true);
    setFase('streaming');
    setPrep(null);
    setProgreso(null);
    setResumen(null);
    setErrorMsg(null);

    void importarMoodleStream(
      { scope, rubrica_id: rubricaId, comision_id: comisionId, materia_id: materiaId },
      {
        onPreparando: (listos, total) => setPrep({ listos, total }),
        onTotal: (total) => {
          setPrep(null);
          setProgreso({ procesadas: 0, total });
        },
        onProgreso: (procesadas, total) => setProgreso({ procesadas, total }),
        onResumen: (r) => {
          setResumen(r);
          setFase('done');
          queryClient.invalidateQueries({ queryKey: PENDIENTES_QUERY_KEY });
          queryClient.invalidateQueries({ queryKey: ['entregas'] });
        },
        onError: (msg) => {
          setErrorMsg(msg);
          setFase('error');
        },
      },
    );
  };

  const handleClose = () => {
    setOpen(false);
    setFase('idle');
    setPrep(null);
    setProgreso(null);
    setResumen(null);
    setErrorMsg(null);
  };

  const btnClasses =
    size === 'sm'
      ? 'flex items-center gap-1 rounded-md bg-accent px-3 py-1.5 text-xs font-medium text-accent-foreground transition-colors hover:bg-accent/80 disabled:opacity-50'
      : 'flex cursor-pointer items-center gap-2 rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-foreground transition-colors hover:bg-accent/80 disabled:cursor-not-allowed disabled:opacity-50';

  const pct = progreso && progreso.total > 0
    ? Math.round((progreso.procesadas / progreso.total) * 100)
    : 0;
  const pctPrep = prep && prep.total > 0
    ? Math.round((prep.listos / prep.total) * 100)
    : 0;

  return (
    <>
      <button onClick={handleClick} disabled={open && fase === 'streaming'} className={btnClasses}>
        <DownloadCloud className={size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'} />
        {label}
      </button>

      <Modal
        isOpen={open}
        onClose={handleClose}
        title={modalTitle}
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
                  Descargando entregas desde Moodle y cargándolas…
                </p>
                <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-center text-sm font-medium text-foreground">
                  Cargando {progreso.procesadas} de {progreso.total}  ({pct}%)
                </p>
              </>
            ) : prep ? (
              <>
                <p className="text-center text-sm text-muted-foreground">
                  Consultando entregas en Moodle…
                </p>
                <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-300"
                    style={{ width: `${pctPrep}%` }}
                  />
                </div>
                <p className="text-center text-sm font-medium text-foreground">
                  Revisando {prep.listos} de {prep.total} unidad{prep.total !== 1 ? 'es' : ''}
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
            <p className="font-semibold text-foreground">No se pudo importar</p>
            <p className="text-sm text-muted-foreground">{errorMsg}</p>
          </div>
        )}

        {fase === 'done' && resumen && <ResumenView data={resumen} />}
      </Modal>
    </>
  );
}

function ResumenView({ data }: { data: ImportarMoodleResponse }) {
  const [showErrores, setShowErrores] = useState(false);

  const chips: { label: string; value: number; className: string }[] = [
    { label: 'Cargadas', value: data.cargadas, className: 'bg-success/10 text-success' },
    { label: 'Re-entregas', value: data.reentregas, className: 'bg-warning/10 text-warning' },
    { label: 'Ya corregidas', value: data.omitidas_ya_corregidas, className: 'bg-muted text-muted-foreground' },
    { label: 'Duplicadas', value: data.duplicadas, className: 'bg-muted text-muted-foreground' },
    { label: 'Sin archivos', value: data.sin_archivos, className: 'bg-muted text-muted-foreground' },
    { label: 'Errores', value: data.errores.length, className: 'bg-destructive/10 text-destructive' },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <CheckCircle className="h-6 w-6 text-success" />
        <p className="font-semibold text-foreground">
          {data.cargadas > 0
            ? `Se cargaron ${data.cargadas} entrega(s) nueva(s)`
            : 'No había entregas nuevas para cargar'}
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

      {data.reentregas > 0 && (
        <p className="rounded-md bg-warning/10 px-3 py-2 text-xs text-warning">
          Hay {data.reentregas} re-entrega(s): el alumno volvió a entregar en Moodle después de
          una corrección. No se sobrescribieron — revisalas manualmente.
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
