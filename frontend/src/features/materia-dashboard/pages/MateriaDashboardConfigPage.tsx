import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Save, Trash2 } from 'lucide-react';
import {
  Button,
  Checkbox,
  HelpButton,
  LoadingState,
} from '@/shared/components/ui';
import { helpContent } from '@/shared/content/helpContent';
import { useMateria } from '@/features/materias/hooks';
import { useCohortes } from '@/features/cohortes/hooks/useCohortes';
import {
  useDashboardConfig,
  useDetectarSecciones,
  useEliminarUnidad,
  useSincronizarUnidades,
  useUnidades,
} from '../hooks/useMateriaDashboard';
import { ConfigForm } from '../components/ConfigForm';

export const MateriaDashboardConfigPage = () => {
  const { materiaId: materiaIdParam } = useParams<{ materiaId: string }>();
  const materiaId = Number(materiaIdParam);

  const { data: materia } = useMateria(materiaId);
  const { data: cohortes } = useCohortes();
  const { data: config, isLoading: loadingConfig } = useDashboardConfig(materiaId);
  const { data: unidades, isLoading: loadingUnidades } = useUnidades(materiaId);

  const detectar = useDetectarSecciones(materiaId);
  const eliminarUnidad = useEliminarUnidad(materiaId);
  const sincronizar = useSincronizarUnidades(materiaId);

  const [seleccionadas, setSeleccionadas] = useState<number[]>([]);

  const handleDetectar = () => {
    detectar.mutate(undefined, {
      onSuccess: (data) => {
        // Pre-tilda: las que el patrón sugiere + las que ya son unidad.
        const yaUnidad = new Set((unidades ?? []).map((u) => u.moodle_section_id));
        setSeleccionadas(
          data.secciones
            .filter((s) => s.es_cabecera_sugerida || yaUnidad.has(s.moodle_section_id))
            .map((s) => s.moodle_section_id)
        );
      },
    });
  };

  const toggle = (id: number) =>
    setSeleccionadas((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );

  // Secciones ordenadas por su orden visual en Moodle (section#).
  const secciones = [...(detectar.data?.secciones ?? [])].sort((a, b) => a.section - b.section);
  // Las tildadas, en ese orden, definen el número de unidad (1..N).
  const tildadasEnOrden = secciones.filter((s) => seleccionadas.includes(s.moodle_section_id));
  const numeroPorSeccion = new Map(
    tildadasEnOrden.map((s, i) => [s.moodle_section_id, i + 1])
  );

  const handleGuardar = () => {
    const payload = tildadasEnOrden.map((s) => ({
      moodle_section_id: s.moodle_section_id,
      nombre: s.nombre,
    }));
    sincronizar.mutate(payload);
  };

  if (loadingConfig || loadingUnidades) {
    return <LoadingState title="Cargando configuración…" />;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/materias"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Volver a Materias
        </Link>
        <div className="mt-2 flex items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground">
            Dashboard · {materia?.codigo ?? `Materia ${materiaId}`}
          </h1>
          <HelpButton title="Ayuda — Config. dashboard" content={helpContent.materiaDashboard} />
        </div>
        {materia?.nombre && <p className="text-sm text-muted-foreground">{materia.nombre}</p>}
      </div>

      {/* Config */}
      {config && cohortes && (
        <ConfigForm
          materiaId={materiaId}
          config={config}
          cohortes={cohortes}
          secciones={detectar.data?.secciones ?? null}
        />
      )}

      {/* Unidades */}
      <div className="rounded-lg border border-border bg-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Unidades de contenido</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Tildá qué secciones de Moodle son las unidades. El orden (de arriba hacia abajo)
              define el número de cada unidad.
            </p>
          </div>
          <Button variant="secondary" onClick={handleDetectar} isLoading={detectar.isPending}>
            <RefreshCw className="h-4 w-4" /> Detectar desde Moodle
          </Button>
        </div>

        {/* Unidades guardadas */}
        {(unidades ?? []).length > 0 && (
          <div className="mt-4 overflow-hidden rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 text-left">Unidad</th>
                  <th className="px-4 py-2 text-left">Sección Moodle</th>
                  <th className="px-4 py-2 text-left">Nombre</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {(unidades ?? []).map((u) => (
                  <tr key={u.id}>
                    <td className="px-4 py-2 font-medium text-foreground">Unidad {u.numero}</td>
                    <td className="px-4 py-2 text-muted-foreground">#{u.moodle_section_id}</td>
                    <td className="px-4 py-2 text-muted-foreground">{u.nombre ?? '—'}</td>
                    <td className="px-4 py-2 text-right">
                      <button
                        onClick={() => eliminarUnidad.mutate(u.id)}
                        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                        aria-label="Eliminar unidad"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Selección desde Moodle (checkboxes sobre TODAS las secciones) */}
        {detectar.data && (
          <div className="mt-4 rounded-lg border border-border">
            <div className="flex items-center justify-between border-b border-border px-4 py-2">
              <span className="text-sm font-medium text-foreground">
                Secciones del curso ({secciones.length}) — tildá las unidades
              </span>
              <Button
                size="sm"
                onClick={handleGuardar}
                isLoading={sincronizar.isPending}
                disabled={tildadasEnOrden.length === 0}
              >
                <Save className="h-4 w-4" /> Guardar unidades ({tildadasEnOrden.length})
              </Button>
            </div>
            <div className="max-h-[420px] divide-y divide-border overflow-auto">
              {secciones.map((s) => {
                const numero = numeroPorSeccion.get(s.moodle_section_id);
                return (
                  <label
                    key={s.moodle_section_id}
                    className="flex cursor-pointer items-center justify-between px-4 py-2.5 transition-colors hover:bg-muted/50"
                  >
                    <div className="flex items-center gap-3">
                      <Checkbox
                        checked={seleccionadas.includes(s.moodle_section_id)}
                        onChange={() => toggle(s.moodle_section_id)}
                      />
                      <span className="text-sm text-foreground">
                        <span className="text-muted-foreground">#{s.section}</span> · {s.nombre}
                      </span>
                    </div>
                    {numero != null && (
                      <span className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
                        Unidad {numero}
                      </span>
                    )}
                  </label>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
