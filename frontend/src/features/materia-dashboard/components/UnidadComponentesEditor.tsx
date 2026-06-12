import { useState } from 'react';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import { Button, Input, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import {
  useActividadesUnidad,
  useSetComponentesUnidad,
} from '../hooks/useMateriaDashboard';
import type {
  FuenteComponente,
  ModoAprobacion,
  TipoComponente,
  Unidad,
} from '../types';

interface Props {
  unidad: Unidad;
  materiaId: number;
}

interface Row {
  key: number;
  tipo: TipoComponente;
  fuente: FuenteComponente;
  cmid: string;
  // Solo aplican cuando fuente=CALIFICACION.
  modo: ModoAprobacion;
  notaMinima: string;
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

const MODO_OPTIONS: SelectOption[] = [
  { value: 'ESCALA', label: 'Escala (Aprobado/Desaprobado)' },
  { value: 'NUMERICO', label: 'Numérica (nota mínima)' },
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
      modo: c.modo_aprobacion ?? 'ESCALA',
      notaMinima: c.nota_minima != null ? String(c.nota_minima) : '',
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
    setRows((rs) => [
      ...rs,
      { key: nextKey(), tipo: 'QUIZ', fuente: 'SEGUIMIENTO', cmid: '', modo: 'ESCALA', notaMinima: '' },
    ]);
  const removeRow = (key: number) => setRows((rs) => rs.filter((r) => r.key !== key));

  // Un componente por calificación NUMÉRICA necesita su nota mínima (igual que el backend).
  const numericoSinNota = rows.some(
    (r) =>
      r.cmid && r.fuente === 'CALIFICACION' && r.modo === 'NUMERICO' && r.notaMinima === ''
  );

  const guardar = () => {
    if (numericoSinNota) return;
    const componentes = rows
      .filter((r) => r.cmid)
      .map((r) => {
        const esCalificacion = r.fuente === 'CALIFICACION';
        const esNumerico = esCalificacion && r.modo === 'NUMERICO';
        return {
          tipo: r.tipo,
          fuente: r.fuente,
          moodle_cmid: Number(r.cmid),
          modo_aprobacion: esCalificacion ? r.modo : ('ESCALA' as ModoAprobacion),
          nota_minima: esNumerico && r.notaMinima !== '' ? Number(r.notaMinima) : null,
        };
      });
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
          // Cada fila en su propia card: en mobile los campos se apilan (no se aprietan
          // en una fila horizontal); en sm+ vuelven a una grilla en línea como en desktop.
          <div
            key={r.key}
            className="space-y-1 rounded-lg border border-border bg-background/40 p-3 sm:border-0 sm:bg-transparent sm:p-0"
          >
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[8rem_12rem_1fr_auto] sm:items-end">
              <Select
                label="Tipo"
                options={TIPO_OPTIONS}
                value={r.tipo}
                onChange={(e) => updateRow(r.key, { tipo: e.target.value as TipoComponente })}
                wrapperClassName="w-full"
              />
              <Select
                label="Fuente"
                options={FUENTE_OPTIONS}
                value={r.fuente}
                onChange={(e) => updateRow(r.key, { fuente: e.target.value as FuenteComponente })}
                wrapperClassName="w-full"
              />
              <Select
                label="Actividad de Moodle"
                options={actividadOptions}
                value={r.cmid}
                onChange={(e) => updateRow(r.key, { cmid: e.target.value })}
                wrapperClassName="w-full"
              />
              <button
                type="button"
                onClick={() => removeRow(r.key)}
                className="flex min-h-11 w-full items-center justify-center gap-1 rounded-md border border-border px-2 text-sm text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive touch-manipulation sm:mb-px sm:w-11 sm:border-0 sm:px-0"
                aria-label="Quitar componente"
              >
                <Trash2 className="h-4 w-4" />
                <span className="sm:hidden">Quitar</span>
              </button>
            </div>
            {r.fuente === 'CALIFICACION' && (
              <div className="grid grid-cols-1 gap-2 pt-1 sm:grid-cols-[16rem_10rem] sm:items-end">
                <Select
                  label="Modo de nota"
                  options={MODO_OPTIONS}
                  value={r.modo}
                  onChange={(e) => updateRow(r.key, { modo: e.target.value as ModoAprobacion })}
                  wrapperClassName="w-full"
                />
                {r.modo === 'NUMERICO' && (
                  <Input
                    label="Nota mínima"
                    type="number"
                    inputMode="decimal"
                    min={0}
                    step="0.01"
                    placeholder="Ej: 6"
                    value={r.notaMinima}
                    onChange={(e) => updateRow(r.key, { notaMinima: e.target.value })}
                  />
                )}
              </div>
            )}
            {aviso && (
              <p className="flex items-start gap-1 text-xs text-amber-600 dark:text-amber-500">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  Esta actividad no tiene seguimiento de finalización: medila por{' '}
                  <strong>Calificación</strong> o no se detectará como realizada.
                </span>
              </p>
            )}
          </div>
        );
      })}

      {numericoSinNota && (
        <p className="flex items-start gap-1 text-xs text-destructive">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            Hay un componente por calificación <strong>numérica</strong> sin nota mínima:
            completala (ej. 6) o cambialo a <strong>Escala</strong> para poder guardar.
          </span>
        </p>
      )}

      <div className="flex flex-col gap-2 pt-1 sm:flex-row sm:items-center sm:justify-between">
        <Button
          size="sm"
          variant="outline"
          onClick={addRow}
          className="w-full sm:w-auto"
        >
          <Plus className="mr-1 h-4 w-4" />
          Agregar componente
        </Button>
        <Button
          size="sm"
          onClick={guardar}
          isLoading={setComp.isPending}
          disabled={numericoSinNota}
          className="w-full sm:w-auto"
        >
          Guardar componentes
        </Button>
      </div>
    </div>
  );
};
