import { useState } from 'react';
import { Pencil, Plus, Trash2, X } from 'lucide-react';
import { Button, Input, ResponsiveTable, Select } from '@/shared/components/ui';
import type { SelectOption, TableColumn } from '@/shared/components/ui';
import {
  useActualizarExamen,
  useCrearExamen,
  useEliminarExamen,
  useExamenes,
} from '../hooks/useMateriaDashboard';
import type {
  ExamenInput,
  ExamenMateria,
  ModoAprobacion,
  TipoActividadMoodle,
  TipoExamen,
} from '../types';
import { TIPOS_RESCATE } from '../types';

interface Props {
  materiaId: number;
}

const TIPO_OPTIONS: SelectOption[] = [
  { value: 'PARCIAL', label: 'Parcial' },
  { value: 'RECUPERATORIO', label: 'Recuperatorio' },
  { value: 'EXTENSION', label: 'Extensión' },
  { value: 'EXTRAORDINARIA', label: 'Extraordinaria' },
  { value: 'GLOBAL', label: 'Global' },
];

const MODO_OPTIONS: SelectOption[] = [
  { value: 'ESCALA', label: 'Escala (Aprobado/Desaprobado)' },
  { value: 'NUMERICO', label: 'Numérico (nota ≥ mínimo)' },
];

const ACTIVIDAD_OPTIONS: SelectOption[] = [
  { value: 'assign', label: 'Tarea' },
  { value: 'quiz', label: 'Cuestionario' },
];

const ACTIVIDAD_LABEL: Record<TipoActividadMoodle, string> = {
  assign: 'Tarea',
  quiz: 'Cuestionario',
};

interface FormState {
  tipo: TipoExamen;
  cmid: string;
  actividad: TipoActividadMoodle;
  modo: ModoAprobacion;
  notaMinima: string;
  recupera: string;
}

const FORM_VACIO: FormState = {
  tipo: 'PARCIAL',
  cmid: '',
  actividad: 'assign',
  modo: 'ESCALA',
  notaMinima: '',
  recupera: '',
};

const esRescate = (tipo: TipoExamen) => TIPOS_RESCATE.includes(tipo);

/**
 * ABM de exámenes de la materia (parciales/recuperatorios/extensiones/extraordinarias/
 * globales). CRUD incremental: cada examen se da de alta por separado para que el vínculo
 * de rescate apunte a ids estables de parciales. La numeración por tipo la asigna el backend.
 */
export const ExamenesEditor = ({ materiaId }: Props) => {
  const { data: examenes, isLoading } = useExamenes(materiaId);
  const crear = useCrearExamen(materiaId);
  const actualizar = useActualizarExamen(materiaId);
  const eliminar = useEliminarExamen(materiaId);

  const [form, setForm] = useState<FormState>(FORM_VACIO);
  const [editId, setEditId] = useState<number | null>(null);

  // Exámenes "principales" (rescatables): un recu/ext/extraordinaria puede recuperar
  // tanto un PARCIAL como un GLOBAL.
  const principales = (examenes ?? []).filter(
    (e) => e.tipo === 'PARCIAL' || e.tipo === 'GLOBAL',
  );
  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const resetForm = () => {
    setForm(FORM_VACIO);
    setEditId(null);
  };

  const cargarParaEditar = (e: ExamenMateria) => {
    setEditId(e.id);
    setForm({
      tipo: e.tipo,
      cmid: String(e.moodle_cmid),
      actividad: e.tipo_actividad ?? 'assign',
      modo: e.modo_aprobacion,
      notaMinima: e.nota_minima != null ? String(e.nota_minima) : '',
      recupera: e.recupera_examen_id != null ? String(e.recupera_examen_id) : '',
    });
  };

  const rescate = esRescate(form.tipo);
  const valido =
    !!form.cmid &&
    (form.modo !== 'NUMERICO' || form.notaMinima !== '') &&
    (!rescate || form.recupera !== '');

  const guardar = () => {
    if (!valido) return;
    const payload: ExamenInput = {
      tipo: form.tipo,
      moodle_cmid: Number(form.cmid),
      tipo_actividad: form.actividad,
      modo_aprobacion: form.modo,
      nota_minima: form.modo === 'NUMERICO' ? Number(form.notaMinima) : null,
      recupera_examen_id: rescate ? Number(form.recupera) : null,
    };
    if (editId != null) {
      actualizar.mutate({ examenId: editId, data: payload }, { onSuccess: resetForm });
    } else {
      crear.mutate(payload, { onSuccess: resetForm });
    }
  };

  const principalOptions: SelectOption[] = [
    { value: '', label: '— elegí el parcial o global que recupera —' },
    ...principales.map((p) => ({ value: String(p.id), label: p.etiqueta })),
  ];

  const etiquetaDe = (id: number | null) =>
    id == null ? null : (examenes ?? []).find((e) => e.id === id)?.etiqueta ?? `#${id}`;

  // Columnas de la tabla de exámenes (desktop). En mobile, ResponsiveTable las
  // apila como cards; la columna de acciones (sticky) cae al pie de la card.
  const examenColumns: TableColumn<ExamenMateria>[] = [
    {
      key: 'etiqueta',
      header: 'Examen',
      render: (e) => <span className="font-medium text-foreground">{e.etiqueta}</span>,
    },
    {
      key: 'cmid',
      header: 'cmid',
      render: (e) => <span className="text-muted-foreground">#{e.moodle_cmid}</span>,
    },
    {
      key: 'actividad',
      header: 'Actividad',
      render: (e) => (
        <span className="text-muted-foreground">
          {ACTIVIDAD_LABEL[e.tipo_actividad ?? 'assign']}
        </span>
      ),
    },
    {
      key: 'aprobacion',
      header: 'Aprobación',
      render: (e) => (
        <span className="text-muted-foreground">
          {e.modo_aprobacion === 'NUMERICO' ? `Nota ≥ ${e.nota_minima}` : 'Escala'}
        </span>
      ),
    },
    {
      key: 'recupera',
      header: 'Recupera',
      render: (e) => (
        <span className="text-muted-foreground">{etiquetaDe(e.recupera_examen_id) ?? '—'}</span>
      ),
    },
    {
      key: 'acciones',
      header: '',
      sticky: true,
      render: (e) => (
        <div className="flex items-center justify-end gap-1">
          <button
            onClick={() => cargarParaEditar(e)}
            className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground touch-manipulation"
            aria-label="Editar examen"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            onClick={() => eliminar.mutate(e.id)}
            className="flex h-11 w-11 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive touch-manipulation"
            aria-label="Eliminar examen"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="rounded-lg border border-border bg-card p-4 sm:p-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Exámenes de la materia</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Dá de alta los exámenes con el <strong>ID de la tarea de Moodle</strong> (cmid). La
          numeración por tipo es automática (Parcial 1, 2…). Recuperatorios, extensiones e
          instancias extraordinarias se vinculan a un parcial o global: si lo aprobás, ese
          parcial o global queda rescatado.
        </p>
      </div>

      {/* Exámenes ya cargados */}
      {isLoading ? (
        <p className="mt-4 text-sm text-muted-foreground">Cargando exámenes…</p>
      ) : (examenes ?? []).length === 0 ? (
        <p className="mt-4 text-sm italic text-muted-foreground">
          Todavía no cargaste exámenes en esta materia.
        </p>
      ) : (
        <div className="mt-4">
          <ResponsiveTable
            columns={examenColumns}
            data={examenes ?? []}
            keyExtractor={(e) => e.id}
          />
        </div>
      )}

      {/* Form de alta / edición */}
      <div className="mt-4 space-y-3 rounded-lg border border-border bg-muted/30 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-foreground">
            {editId != null ? 'Editar examen' : 'Agregar examen'}
          </span>
          {editId != null && (
            <button
              onClick={resetForm}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" /> Cancelar edición
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 items-end gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Select
            label="Tipo"
            options={TIPO_OPTIONS}
            value={form.tipo}
            onChange={(ev) => set({ tipo: ev.target.value as TipoExamen })}
            wrapperClassName="w-full"
          />
          <Input
            label="ID de la tarea (cmid)"
            type="number"
            inputMode="numeric"
            pattern="[0-9]*"
            value={form.cmid}
            onChange={(ev) => set({ cmid: ev.target.value })}
            placeholder="17459"
            wrapperClassName="w-full"
          />
          <Select
            label="Actividad de Moodle"
            options={ACTIVIDAD_OPTIONS}
            value={form.actividad}
            onChange={(ev) => set({ actividad: ev.target.value as TipoActividadMoodle })}
            wrapperClassName="w-full"
          />
          <Select
            label="Aprobación"
            options={MODO_OPTIONS}
            value={form.modo}
            onChange={(ev) => set({ modo: ev.target.value as ModoAprobacion })}
            wrapperClassName="w-full sm:col-span-2 lg:col-span-1"
          />
          {form.modo === 'NUMERICO' && (
            <Input
              label="Nota mínima"
              type="number"
              inputMode="decimal"
              step="0.01"
              value={form.notaMinima}
              onChange={(ev) => set({ notaMinima: ev.target.value })}
              placeholder="6"
              wrapperClassName="w-full"
            />
          )}
          {rescate && (
            <Select
              label="Recupera el parcial o global"
              options={principalOptions}
              value={form.recupera}
              onChange={(ev) => set({ recupera: ev.target.value })}
              wrapperClassName="w-full sm:col-span-2"
            />
          )}
        </div>

        {rescate && principales.length === 0 && (
          <p className="text-xs text-amber-600 dark:text-amber-500">
            No hay parciales ni globales cargados todavía. Cargá primero el parcial o global que
            este examen recupera.
          </p>
        )}

        <div className="flex justify-end">
          <Button
            size="sm"
            onClick={guardar}
            disabled={!valido}
            isLoading={crear.isPending || actualizar.isPending}
            className="w-full sm:w-auto"
          >
            <Plus className="mr-1 h-4 w-4" />
            {editId != null ? 'Guardar cambios' : 'Agregar examen'}
          </Button>
        </div>
      </div>
    </div>
  );
};
