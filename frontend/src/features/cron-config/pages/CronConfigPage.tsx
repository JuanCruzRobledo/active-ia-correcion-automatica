import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { Play } from 'lucide-react';
import { Button, Checkbox, HelpButton, LoadingState, Spinner } from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { useUsuarios } from '@/features/usuarios/hooks';
import { CronConfigForm } from '../components/CronConfigForm';
import { useCronConfig, useMateriasConfiguradas } from '../hooks/useCronConfig';
import { dispararSnapshotStream } from '../services/cron-config.service';
import { formatFechaHoraArg } from '@/shared/utils/fecha';

interface Progreso {
  procesados: number;
  total: number;
  materiaIdx: number;
  materiasTotal: number;
}

const fmtFecha = (iso: string | null) =>
  iso ? formatFechaHoraArg(iso) : 'Nunca generado';

export const CronConfigPage = () => {
  const { data: config, isLoading: loadingConfig } = useCronConfig();
  const { data: usuariosData, isLoading: loadingUsuarios } = useUsuarios({
    rol: 'TODOS',
    activo: true,
    search: '',
    page: 1,
    per_page: 100,
  });
  const { data: materias, isLoading: loadingMaterias } = useMateriasConfiguradas();

  const qc = useQueryClient();
  const [seleccionadas, setSeleccionadas] = useState<number[]>([]);
  const [running, setRunning] = useState(false);
  const [progreso, setProgreso] = useState<Progreso | null>(null);
  const [terminado, setTerminado] = useState<number | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const toggle = (id: number) =>
    setSeleccionadas((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  const todasIds = (materias ?? []).map((m) => m.materia_id);
  const todasSeleccionadas = todasIds.length > 0 && seleccionadas.length === todasIds.length;
  const toggleTodas = () =>
    setSeleccionadas(todasSeleccionadas ? [] : todasIds);

  const handleGenerar = async () => {
    if (seleccionadas.length === 0) return;
    setRunning(true);
    setProgreso(null);
    setTerminado(null);
    setErrorMsg(null);
    const controller = new AbortController();
    try {
      await dispararSnapshotStream(
        seleccionadas,
        (e) => {
          if (e.tipo === 'progreso') {
            setProgreso({
              procesados: e.procesados ?? 0,
              total: e.total ?? 0,
              materiaIdx: e.materia_idx ?? 1,
              materiasTotal: e.materias_total ?? 1,
            });
          } else if (e.tipo === 'done') {
            setTerminado(e.materias ?? 0);
            toast.success('Snapshots generados');
            qc.invalidateQueries({ queryKey: ['dashboard-gestor'] });
            qc.invalidateQueries({ queryKey: ['cron-config', 'materias-configuradas'] });
          } else if (e.tipo === 'error') {
            setErrorMsg(e.detalle ?? 'Error generando el snapshot');
          }
        },
        controller.signal
      );
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Error de conexión');
    } finally {
      setRunning(false);
    }
  };

  if (loadingConfig || loadingUsuarios) {
    return <LoadingState title="Cargando configuración…" />;
  }

  const pct =
    progreso && progreso.total > 0
      ? Math.round((progreso.procesados / progreso.total) * 100)
      : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">Snapshots del dashboard</h1>
          <HelpButton title="Ayuda — Snapshots / Cron" content={helpContent.cronConfig} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Programá la actualización automática del dashboard de gestores y generá snapshots
          a mano para las materias que elijas.
        </p>
      </div>

      {/* Form de config */}
      {config && <CronConfigForm config={config} usuarios={usuariosData?.items ?? []} />}

      {/* Generación manual por materia */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Generar snapshots ahora</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Elegí qué materias recalcular (con tus credenciales de Moodle). Cada una muestra
              cuándo se generó por última vez.
            </p>
          </div>
          {(materias ?? []).length > 0 && (
            <button
              onClick={toggleTodas}
              disabled={running}
              className="text-sm text-accent transition-colors hover:underline disabled:opacity-50"
            >
              {todasSeleccionadas ? 'Quitar todas' : 'Seleccionar todas'}
            </button>
          )}
        </div>

        {/* Lista de materias */}
        <div className="mt-4 space-y-2">
          {loadingMaterias ? (
            <div className="flex items-center gap-2 py-6 text-sm text-muted-foreground">
              <Spinner /> Cargando materias…
            </div>
          ) : (materias ?? []).length === 0 ? (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No hay materias configuradas. Configurá cohorte, unidad actual y unidades en cada materia.
            </p>
          ) : (
            (materias ?? []).map((m) => (
              <label
                key={m.materia_id}
                className="flex cursor-pointer items-center justify-between rounded-lg border border-border px-4 py-3 transition-colors hover:bg-muted/50"
              >
                <div className="flex items-center gap-3">
                  <Checkbox
                    checked={seleccionadas.includes(m.materia_id)}
                    onChange={() => toggle(m.materia_id)}
                    disabled={running}
                  />
                  <div>
                    <span className="font-medium text-foreground">{m.codigo}</span>
                    <span className="text-muted-foreground"> · {m.nombre}</span>
                  </div>
                </div>
                <span className="text-xs text-muted-foreground">
                  Último: {fmtFecha(m.ultimo_snapshot)}
                  {m.total_alumnos != null && ` · ${m.total_alumnos} alumnos`}
                </span>
              </label>
            ))
          )}
        </div>

        {/* Acción */}
        <div className="mt-4 flex justify-end">
          <Button
            onClick={handleGenerar}
            isLoading={running}
            disabled={running || seleccionadas.length === 0}
          >
            <Play className="h-4 w-4" /> Generar seleccionadas ({seleccionadas.length})
          </Button>
        </div>

        {/* Barra de progreso */}
        {running && progreso && (
          <div className="mt-4">
            <div className="mb-1 flex justify-between text-sm text-muted-foreground">
              <span>
                Materia {progreso.materiaIdx}/{progreso.materiasTotal}
              </span>
              <span>
                {progreso.procesados}/{progreso.total} alumnos ({pct}%)
              </span>
            </div>
            <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-2.5 rounded-full bg-accent transition-all duration-300"
                style={{ width: `${pct}%` }}
              />
            </div>
          </div>
        )}

        {/* Resultado */}
        {terminado != null && !running && (
          <div className="mt-4 rounded-lg border border-success/30 bg-success/10 p-4 text-sm text-foreground">
            ✅ Listo: se generaron snapshots de <strong>{terminado}</strong> materia(s). El dashboard ya está actualizado.
          </div>
        )}
        {errorMsg && !running && (
          <div className="mt-4 rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-sm text-foreground">
            ❌ {errorMsg}
          </div>
        )}
      </div>
    </div>
  );
};
