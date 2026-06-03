import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useChartColors } from '../hooks/useChartColors';
import { ESTADO_LABEL, ESTADOS_ORDEN } from '../constants';
import type { ConteoEstados, EstadoAvance } from '../types';

interface EstadoPieProps {
  conteos: ConteoEstados;
  onSlice: (estado: EstadoAvance) => void;
}

const CAMPO: Record<EstadoAvance, keyof ConteoEstados> = {
  AL_DIA: 'al_dia',
  RIESGO_MEDIO: 'riesgo_medio',
  RIESGO_ALTO: 'riesgo_alto',
  SIN_ACTIVIDAD: 'sin_actividad',
};

/** Gráfico de torta del avance: porción clickeable + leyenda con el conteo de cada estado. */
export const EstadoPie = ({ conteos, onSlice }: EstadoPieProps) => {
  const colors = useChartColors();

  const data = ESTADOS_ORDEN.map((estado) => ({
    estado,
    label: ESTADO_LABEL[estado],
    value: conteos[CAMPO[estado]],
  })).filter((d) => d.value > 0);

  if (data.length === 0) {
    return (
      <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">
        No hay alumnos para esta selección.
      </div>
    );
  }

  return (
    <div>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={70}
            outerRadius={120}
            paddingAngle={2}
            onClick={(_, index) => onSlice(data[index].estado)}
          >
            {data.map((d) => (
              <Cell key={d.estado} fill={colors[d.estado]} cursor="pointer" />
            ))}
          </Pie>
          <Tooltip
            formatter={(value, name) => [`${value} alumno(s)`, name]}
            contentStyle={{
              background: 'oklch(var(--popover))',
              border: '1px solid oklch(var(--border))',
              borderRadius: 8,
              color: 'oklch(var(--popover-foreground))',
            }}
            itemStyle={{ color: 'oklch(var(--popover-foreground))' }}
          />
        </PieChart>
      </ResponsiveContainer>

      {/* Leyenda con el conteo por estado (clickeable, igual que la torta) */}
      <div className="mt-3 flex flex-wrap justify-center gap-x-6 gap-y-2">
        {data.map((d) => (
          <button
            key={d.estado}
            onClick={() => onSlice(d.estado)}
            className="flex items-center gap-2 text-sm transition-opacity hover:opacity-80"
          >
            <span
              className="h-3 w-3 shrink-0 rounded-sm"
              style={{ backgroundColor: colors[d.estado] }}
            />
            <span className="text-muted-foreground">{d.label}</span>
            <span className="font-semibold text-foreground">{d.value}</span>
          </button>
        ))}
      </div>
    </div>
  );
};
