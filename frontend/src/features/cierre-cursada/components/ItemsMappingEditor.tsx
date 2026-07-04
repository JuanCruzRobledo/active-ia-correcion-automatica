import { useEffect, useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button, Checkbox, Input, Select } from '@/shared/components/ui';
import type { SelectOption } from '@/shared/components/ui';
import { useConfirmarMapping } from '../hooks/useCierreCursada';
import type { CategoriaItemCierre, CierreItemSugerido } from '../types';

interface Props {
  materiaId: number;
  cuatrimestreId: number;
  items: CierreItemSugerido[];
}

interface Row {
  moodle_cmid: number;
  nombre_moodle: string;
  orden: number | null;
  categoria: CategoriaItemCierre;
  unidad: string;
  opcional: boolean;
}

const CATEGORIA_OPTIONS: SelectOption[] = [
  { value: 'TP', label: 'TP (Actividad de cierre)' },
  { value: 'AUTOEVAL', label: 'Autoevaluación' },
  { value: 'PARCIAL_1', label: 'Parcial 1' },
  { value: 'PARCIAL_2', label: 'Parcial 2' },
  { value: 'TPI', label: 'TPI' },
  { value: 'IGNORAR', label: 'Ignorar' },
];

const rowsFromItems = (items: CierreItemSugerido[]): Row[] =>
  items.map((i) => ({
    moodle_cmid: i.moodle_cmid,
    nombre_moodle: i.nombre_moodle,
    orden: i.orden,
    categoria: i.categoria,
    unidad: i.unidad != null ? String(i.unidad) : '',
    opcional: i.opcional,
  }));

/**
 * Tabla editable del mapeo de ítems del calificador: 1 fila = 1 ítem de
 * Moodle, con la categoría/unidad/opcional PRE-cargadas por sugerencia
 * (regex) o por el mapeo ya confirmado antes. El coordinador revisa/corrige
 * y confirma — nunca se genera el cierre con una sugerencia sin revisar.
 */
export const ItemsMappingEditor = ({ materiaId, cuatrimestreId, items }: Props) => {
  const [rows, setRows] = useState<Row[]>(() => rowsFromItems(items));
  const confirmar = useConfirmarMapping(materiaId, cuatrimestreId);

  // Si cambia la materia/cuatrimestre (nueva query), reinicia con los datos frescos.
  useEffect(() => {
    setRows(rowsFromItems(items));
  }, [items]);

  const updateRow = (cmid: number, patch: Partial<Row>) =>
    setRows((rs) => rs.map((r) => (r.moodle_cmid === cmid ? { ...r, ...patch } : r)));

  const sinConfirmar = items.filter((i) => !i.confirmado).length;

  const guardar = () => {
    confirmar.mutate(
      rows.map((r) => ({
        moodle_cmid: r.moodle_cmid,
        nombre_moodle: r.nombre_moodle,
        categoria: r.categoria,
        unidad: r.unidad !== '' ? Number(r.unidad) : null,
        opcional: r.opcional,
        orden: r.orden,
      }))
    );
  };

  return (
    <div className="space-y-3 rounded-lg border border-border bg-muted/30 p-4">
      {sinConfirmar > 0 && (
        <p className="flex items-start gap-1 text-sm text-amber-600 dark:text-amber-500">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Hay <strong>{sinConfirmar}</strong> ítem(s) con categoría sugerida sin confirmar
            todavía — revisalos antes de generar el cierre.
          </span>
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-border text-left text-muted-foreground">
              <th className="py-2 pr-2">Ítem de Moodle</th>
              <th className="py-2 pr-2">Categoría</th>
              <th className="py-2 pr-2">Unidad</th>
              <th className="py-2 pr-2">Opcional</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.moodle_cmid} className="border-b border-border/60">
                <td className="py-2 pr-2 align-middle">{r.nombre_moodle}</td>
                <td className="py-2 pr-2 align-middle">
                  <Select
                    options={CATEGORIA_OPTIONS}
                    value={r.categoria}
                    onChange={(e) =>
                      updateRow(r.moodle_cmid, { categoria: e.target.value as CategoriaItemCierre })
                    }
                    wrapperClassName="w-full min-w-[13rem]"
                  />
                </td>
                <td className="py-2 pr-2 align-middle">
                  <Input
                    type="number"
                    inputMode="numeric"
                    min={1}
                    value={r.unidad}
                    onChange={(e) => updateRow(r.moodle_cmid, { unidad: e.target.value })}
                    className="w-20"
                  />
                </td>
                <td className="py-2 pr-2 align-middle">
                  <Checkbox
                    checked={r.opcional}
                    onChange={(e) => updateRow(r.moodle_cmid, { opcional: e.target.checked })}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Button size="sm" onClick={guardar} isLoading={confirmar.isPending}>
        Confirmar mapeo
      </Button>
    </div>
  );
};
