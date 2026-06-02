import { Search, Download } from 'lucide-react';
import type { AgruparPor, FiltrosDisponibles, FiltrosGestion } from '../types';
import { botonAccionCls } from './botonAccion';

interface Props {
  opciones: FiltrosDisponibles;
  filtros: FiltrosGestion;
  onChange: (f: FiltrosGestion) => void;
  onConsultar: () => void;
  onDescargar: (agruparPor: AgruparPor) => void;
  consultando: boolean;
  descargando: AgruparPor | null;
  /** Deshabilita TODOS los botones mientras hay alguna operación en curso. */
  bloqueado: boolean;
}

function toggle(arr: string[], val: string): string[] {
  return arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val];
}

const SELECT_CLS =
  'w-full rounded-md border border-border bg-card px-3 py-2 text-sm text-foreground';
const LABEL_CLS = 'mb-1 block text-sm font-medium text-muted-foreground';

export function FiltrosGestionForm({
  opciones,
  filtros,
  onChange,
  onConsultar,
  onDescargar,
  consultando,
  descargando,
  bloqueado,
}: Props) {
  const set = (parcial: Partial<FiltrosGestion>) =>
    onChange({ ...filtros, ...parcial });

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {/* Rol */}
        <div>
          <label className={LABEL_CLS}>Rol</label>
          <select
            className={SELECT_CLS}
            value={filtros.rol ?? ''}
            onChange={(e) => set({ rol: e.target.value || null })}
          >
            <option value="">Todos</option>
            {opciones.roles.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Estatus */}
        <div>
          <label className={LABEL_CLS}>Estatus</label>
          <select
            className={SELECT_CLS}
            value={filtros.estatus ?? ''}
            onChange={(e) => set({ estatus: e.target.value || null })}
          >
            <option value="">Todos</option>
            {opciones.estatus.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        {/* Inactividad */}
        <div>
          <label className={LABEL_CLS}>Inactividad</label>
          <select
            className={SELECT_CLS}
            value={filtros.inactividad_tipo ?? ''}
            onChange={(e) => set({ inactividad_tipo: e.target.value || null })}
          >
            <option value="">Sin filtro</option>
            {opciones.inactividad.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          {filtros.inactividad_tipo === 'rango' && (
            <div className="mt-2 flex items-center gap-2">
              <input
                type="number"
                min={0}
                placeholder="desde (días)"
                className={SELECT_CLS}
                value={filtros.inactividad_desde ?? ''}
                onChange={(e) =>
                  set({
                    inactividad_desde: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
              <span className="text-muted-foreground">a</span>
              <input
                type="number"
                min={0}
                placeholder="hasta (días)"
                className={SELECT_CLS}
                value={filtros.inactividad_hasta ?? ''}
                onChange={(e) =>
                  set({
                    inactividad_hasta: e.target.value ? Number(e.target.value) : null,
                  })
                }
              />
            </div>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <MultiSelect
          titulo="Regionales"
          opciones={opciones.regionales}
          seleccionadas={filtros.regionales}
          onToggle={(v) => set({ regionales: toggle(filtros.regionales, v) })}
        />
        <MultiSelect
          titulo="Comisiones"
          opciones={opciones.comisiones}
          seleccionadas={filtros.comisiones}
          onToggle={(v) => set({ comisiones: toggle(filtros.comisiones, v) })}
        />
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button onClick={onConsultar} disabled={bloqueado} className={botonAccionCls(consultando)}>
          <Search className="h-4 w-4" />
          {consultando ? 'Consultando…' : 'Consultar'}
        </button>
        <button
          onClick={() => onDescargar('regional')}
          disabled={bloqueado}
          className={botonAccionCls(descargando === 'regional')}
        >
          <Download className="h-4 w-4" />
          {descargando === 'regional' ? 'Generando…' : 'Excel para Nexos'}
        </button>
        <button
          onClick={() => onDescargar('comision')}
          disabled={bloqueado}
          className={botonAccionCls(descargando === 'comision')}
        >
          <Download className="h-4 w-4" />
          {descargando === 'comision' ? 'Generando…' : 'Excel para Tutores'}
        </button>
      </div>
    </div>
  );
}

interface MultiSelectProps {
  titulo: string;
  opciones: string[];
  seleccionadas: string[];
  onToggle: (v: string) => void;
}

function MultiSelect({ titulo, opciones, seleccionadas, onToggle }: MultiSelectProps) {
  return (
    <div>
      <label className={LABEL_CLS}>
        {titulo}
        {seleccionadas.length > 0 && (
          <span className="ml-1 text-xs text-accent">({seleccionadas.length})</span>
        )}
      </label>
      <div className="max-h-40 space-y-1 overflow-auto rounded-md border border-border bg-card p-2">
        {opciones.length === 0 && (
          <p className="px-1 text-xs text-muted-foreground">Sin opciones</p>
        )}
        {opciones.map((op) => (
          <label
            key={op}
            className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm text-foreground hover:bg-muted"
          >
            <input
              type="checkbox"
              checked={seleccionadas.includes(op)}
              onChange={() => onToggle(op)}
            />
            {op}
          </label>
        ))}
      </div>
    </div>
  );
}
