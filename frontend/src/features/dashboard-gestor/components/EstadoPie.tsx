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
      <div className="flex h-60 items-center justify-center text-sm text-muted-foreground sm:h-[320px]">
        No hay alumnos para esta selección.
      </div>
    );
  }

  return (
    <div>
      {/* Alto y radios responsive: en mobile más compacto y en porcentaje para
          que la torta sea legible en pantallas chicas; en sm: el look actual. */}
      <div className="h-60 sm:h-[300px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              nameKey="label"
              innerRadius="55%"
              outerRadius="80%"
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
      </div>

      {/* Leyenda con el conteo por estado (clickeable, igual que la torta).
          En mobile es el medio principal de interacción → targets táctiles. */}
      <div className="mt-3 flex flex-wrap justify-center gap-x-4 gap-y-1 sm:gap-x-6 sm:gap-y-2">
        {data.map((d) => (
          <button
            key={d.estado}
            onClick={() => onSlice(d.estado)}
            className="flex min-h-11 items-center gap-2 px-2 py-1.5 text-sm transition-opacity hover:opacity-80 touch-manipulation sm:min-h-0 sm:px-0 sm:py-0"
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
