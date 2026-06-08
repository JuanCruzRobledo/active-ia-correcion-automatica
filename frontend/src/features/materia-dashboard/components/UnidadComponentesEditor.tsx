import { useState } from 'react';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { Button, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import {
  useActividadesUnidad,
  useSetComponentesUnidad,
} from '../hooks/useMateriaDashboard';
import type { FuenteComponente, TipoComponente, Unidad } from '../types';

interface Props {
  unidad: Unidad;
  materiaId: number;
}

interface Row {
  key: number;
  tipo: TipoComponente;
  fuente: FuenteComponente;
  cmid: string;
}

const TIPO_OPTIONS: SelectOption[] = [
  { value: 'TP', label: 'TP' },
  { value: 'QUIZ', label: 'Quiz' },
  { value: 'AUTOEVALUACION', label: 'Autoevaluación' },
  { value: 'CIERRE', label: 'Cierre' },
];

const FUENTE_OPTIONS: SelectOption[] = [
  { value: 'SEGUIMIENTO', label: 'Seguimiento (completó)' },
  { value: 'CALIFICACION', label: 'Calificación (nota)' },
];

// Contador local para keys estables de filas nuevas (no son ids de servidor).
let _seq = 0;
const nextKey = () => ++_seq;

/**
 * Editor de los componentes evaluables DINÁMICOS de una unidad (§9.bis F).
 * Cada fila = tipo (etiqueta) + fuente (cómo se mide) + actividad de Moodle.
 * Se pueden agregar/quitar N filas, incluso varias del mismo tipo. Guardar reemplaza
 * el set completo. Avisa si elegís una actividad sin seguimiento para medir por seguimiento.
 */
export const UnidadComponentesEditor = ({ unidad, materiaId }: Props) => {
  const { data: actividades, isLoading, error } = useActividadesUnidad(unidad.id, true);
  const setComp = useSetComponentesUnidad(materiaId);

  const [rows, setRows] = useState<Row[]>(() =>
    unidad.componentes.map((c) => ({
      key: nextKey(),
      tipo: c.tipo,
      fuente: c.fuente,
      cmid: String(c.moodle_cmid),
    }))
  );

  if (isLoading) {
    return <p className="p-4 text-sm text-muted-foreground">Cargando actividades de Moodle…</p>;
  }
  if (error) {
    return (
      <p className="p-4 text-sm text-destructive">
        No se pudieron cargar las actividades (¿credenciales de Moodle en tu perfil?).
      </p>
    );
  }

  const actividadOptions: SelectOption[] = [
    { value: '', label: '— elegí una actividad —' },
    ...(actividades ?? []).map((a) => ({
      value: String(a.cmid),
      label: `${a.nombre} · ${a.modname}${a.tiene_seguimiento ? '' : ' (sin seguimiento)'}`,
    })),
  ];

  const sinSeguimiento = (cmid: string) =>
    !!cmid && (actividades ?? []).some((a) => String(a.cmid) === cmid && !a.tiene_seguimiento);

  const updateRow = (key: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.key === key ? { ...r, ...patch } : r)));
  const addRow = () =>
    setRows((rs) => [...rs, { key: nextKey(), tipo: 'QUIZ', fuente: 'SEGUIMIENTO', cmid: '' }]);
  const removeRow = (key: number) => setRows((rs) => rs.filter((r) => r.key !== key));

  const guardar = () => {
    const componentes = rows
      .filter((r) => r.cmid)
      .map((r) => ({ tipo: r.tipo, fuente: r.fuente, moodle_cmid: Number(r.cmid) }));
    setComp.mutate({ unidadId: unidad.id, data: { componentes } });
  };

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-4">
      <p className="text-sm text-muted-foreground">
        Componentes evaluables de la{' '}
        <strong className="text-foreground">Unidad {unidad.numero}</strong>. Agregá los que
        tenga (TP, quizzes, autoevaluación, cierre). La <strong>fuente</strong> define cómo se
        sabe si está hecho: por <em>seguimiento</em> (completó la actividad) o por{' '}
        <em>calificación</em> (tiene nota).
      </p>

      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground italic">
          Esta unidad no tiene componentes. Agregá uno o dejala vacía si es opcional.
        </p>
      )}

      {rows.map((r) => {
        const aviso = r.fuente === 'SEGUIMIENTO' && sinSeguimiento(r.cmid);
        return (
          <div key={r.key} className="space-y-1">
            <div className="flex flex-wrap items-end gap-2">
              <Select
                label="Tipo"
                options={TIPO_OPTIONS}
                value={r.tipo}
                onChange={(e) => updateRow(r.key, { tipo: e.target.value as TipoComponente })}
                wrapperClassName="w-36"
              />
              <Select
                label="Fuente"
                options={FUENTE_OPTIONS}
                value={r.fuente}
                onChange={(e) => updateRow(r.key, { fuente: e.target.value as FuenteComponente })}
                wrapperClassName="w-48"
              />
              <Select
                label="Actividad de Moodle"
                options={actividadOptions}
                value={r.cmid}
                onChange={(e) => updateRow(r.key, { cmid: e.target.value })}
                wrapperClassName="min-w-[16rem] flex-1"
              />
              <button
                type="button"
                onClick={() => removeRow(r.key)}
                className="mb-1 rounded-md p-2 text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
                aria-label="Quitar componente"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
            {aviso && (
              <p className="flex items-center gap-1 text-xs text-amber-600 dark:text-amber-500">
                <AlertTriangle className="h-3.5 w-3.5" />
                Esta actividad no tiene seguimiento de finalización: medila por{' '}
                <strong>Calificación</strong> o no se detectará como realizada.
              </p>
            )}
          </div>
        );
      })}

      <div className="flex items-center justify-between pt-1">
        <Button size="sm" variant="outline" onClick={addRow}>
          <Plus className="mr-1 h-4 w-4" />
          Agregar componente
        </Button>
        <Button size="sm" onClick={guardar} isLoading={setComp.isPending}>
          Guardar componentes
        </Button>
      </div>
    </div>
  );
};
