import type { EstadoAvance } from './types';

export const ESTADO_LABEL: Record<EstadoAvance, string> = {
  AL_DIA: 'Al día',
  RIESGO_MEDIO: 'Riesgo medio',
  RIESGO_ALTO: 'Riesgo alto',
  SIN_ACTIVIDAD: 'Sin actividad',
};

export const ESTADOS_ORDEN: EstadoAvance[] = [
  'AL_DIA',
  'RIESGO_MEDIO',
  'RIESGO_ALTO',
  'SIN_ACTIVIDAD',
];
