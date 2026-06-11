import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw, Save, SlidersHorizontal, Trash2 } from 'lucide-react';
import {
  Button,
  Checkbox,
  ConfirmDialog,
  HelpButton,
  LoadingState,
  ResponsiveTable,
} from '@/shared/components/ui';
import type { TableColumn } from '@/shared/components/ui';
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
import type { Unidad } from '../types';
import { ConfigForm } from '../components/ConfigForm';
import { ExamenesEditor } from '../components/ExamenesEditor';
import { UnidadComponentesEditor } from '../components/UnidadComponentesEditor';

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
  const [unidadComp, setUnidadComp] = useState<number | null>(null);
  const [unidadAEliminar, setUnidadAEliminar] = useState<Unidad | null>(null);

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

  // Columnas de la tabla de unidades guardadas (desktop). En mobile, ResponsiveTable
  // las apila como cards. La columna de acciones es sticky a la derecha en desktop y
  // pasa al pie de la card en mobile.
  const unidadColumns: TableColumn<Unidad>[] = [
    {
      key: 'unidad',
      header: 'Unidad',
      render: (u) => (
        <span className="font-medium text-foreground">Unidad {u.numero}</span>
      ),
    },
    {
      key: 'seccion',
      header: 'Sección Moodle',
      render: (u) => (
        <span className="text-muted-foreground">#{u.moodle_section_id}</span>
      ),
    },
    {
      key: 'nombre',
      header: 'Nombre',
      render: (u) => <span className="text-muted-foreground">{u.nombre ?? '—'}</span>,
    },
    {
      key: 'acciones',
      header: '',
      sticky: true,
      render: (u) => {
        const comps = u.componentes?.length ?? 0;
        return (
          <div className="flex items-center justify-end gap-1">
            <span className="mr-1 text-xs text-muted-foreground">
              {comps} {comps === 1 ? 'componente' : 'componentes'}
            </span>
            <button
              onClick={() => setUnidadComp(unidadComp === u.id ? null : u.id)}
              className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground touch-manipulation"
              aria-label="Configurar componentes"
            >
              <SlidersHorizontal className="h-4 w-4" />
            </button>
            <button
              onClick={() => setUnidadAEliminar(u)}
              className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive touch-manipulation"
              aria-label="Eliminar unidad"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          </div>
        );
      },
    },
  ];

  if (loadingConfig || loadingUnidades) {
    return <LoadingState title="Cargando configuración…" />;
  }

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Header */}
      <div>
        <Link
          to="/materias"
          className="inline-flex min-h-11 items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground touch-manipulation"
        >
          <ArrowLeft className="h-4 w-4" /> Volver a Materias
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-bold text-foreground sm:text-3xl">
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
      <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Unidades de contenido</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Tildá qué secciones de Moodle son las unidades. El orden (de arriba hacia abajo)
              define el número de cada unidad.
            </p>
          </div>
          <Button
            variant="secondary"
            onClick={handleDetectar}
            isLoading={detectar.isPending}
            className="w-full sm:w-auto"
          >
            <RefreshCw className="h-4 w-4" /> Detectar desde Moodle
          </Button>
        </div>

        {/* Unidades guardadas */}
        {(unidades ?? []).length > 0 && (
          <div className="mt-4">
            <ResponsiveTable
              columns={unidadColumns}
              data={unidades ?? []}
              keyExtractor={(u) => u.id}
            />
          </div>
        )}

        {/* Editor de componentes (TP/autoeval/cierre) de la unidad expandida */}
        {unidadComp != null && (
          <div className="mt-3">
            {(() => {
              const u = (unidades ?? []).find((x) => x.id === unidadComp);
              return u ? (
                // key={u.id}: fuerza el REMONTE al cambiar de unidad, así el estado
                // local del editor (rows) se re-inicializa con los componentes de ESA
                // unidad. Sin esto, React reusa la instancia y queda el estado viejo.
                <UnidadComponentesEditor key={u.id} unidad={u} materiaId={materiaId} />
              ) : null;
            })()}
          </div>
        )}

        {/* Selección desde Moodle (checkboxes sobre TODAS las secciones) */}
        {detectar.data && (
          <div className="mt-4 rounded-lg border border-border">
            <div className="flex flex-col gap-2 border-b border-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-2">
              <span className="text-sm font-medium text-foreground">
                Secciones del curso ({secciones.length}) — tildá las unidades
              </span>
              <Button
                size="sm"
                onClick={handleGuardar}
                isLoading={sincronizar.isPending}
                disabled={tildadasEnOrden.length === 0}
                className="w-full sm:w-auto"
              >
                <Save className="h-4 w-4" /> Guardar unidades ({tildadasEnOrden.length})
              </Button>
            </div>
            <div className="max-h-[60vh] divide-y divide-border overflow-auto scroll-momentum sm:max-h-[420px]">
              {secciones.map((s) => {
                const numero = numeroPorSeccion.get(s.moodle_section_id);
                return (
                  <label
                    key={s.moodle_section_id}
                    className="flex min-h-11 cursor-pointer items-center justify-between gap-3 px-4 py-3 transition-colors hover:bg-muted/50 touch-manipulation sm:py-2.5"
                  >
                    <div className="flex min-w-0 items-center gap-3">
                      <Checkbox
                        checked={seleccionadas.includes(s.moodle_section_id)}
                        onChange={() => toggle(s.moodle_section_id)}
                      />
                      <span className="min-w-0 truncate text-sm text-foreground">
                        <span className="text-muted-foreground">#{s.section}</span> · {s.nombre}
                      </span>
                    </div>
                    {numero != null && (
                      <span className="shrink-0 rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
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

      {/* Exámenes de la materia (parciales/recuperatorios/extensiones/extraordinarias/globales) */}
      <ExamenesEditor materiaId={materiaId} />

      {/* Confirmación de borrado de unidad (reemplaza acción directa, en bottom-sheet mobile) */}
      <ConfirmDialog
        isOpen={unidadAEliminar != null}
        onClose={() => setUnidadAEliminar(null)}
        onConfirm={() => {
          if (unidadAEliminar) {
            eliminarUnidad.mutate(unidadAEliminar.id, {
              onSuccess: () => setUnidadAEliminar(null),
            });
          }
        }}
        title="Eliminar unidad"
        message={
          unidadAEliminar
            ? `¿Seguro que querés eliminar la Unidad ${unidadAEliminar.numero}? Esta acción no se puede deshacer.`
            : ''
        }
        confirmLabel="Eliminar"
        variant="destructive"
        isLoading={eliminarUnidad.isPending}
      />
    </div>
  );
};
