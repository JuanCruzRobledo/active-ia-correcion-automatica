import { useTheme } from '@/shared/hooks/useTheme';
import type { EstadoAvance } from '../types';

// Fallbacks (por si getComputedStyle no resuelve las CSS vars).
const FALLBACK: Record<EstadoAvance, string> = {
  AL_DIA: '#16a34a',
  RIESGO_MEDIO: '#d97706',
  RIESGO_ALTO: '#dc2626',
  SIN_ACTIVIDAD: '#6b7280',
};

/**
 * Colores del gráfico tomados de los tokens del design system (OKLCH).
 * Se leen en runtime, así respetan el tema actual; `useTheme()` fuerza el
 * re-render (y la relectura) cuando se cambia claro/oscuro.
 */
export function useChartColors(): Record<EstadoAvance, string> {
  const { theme } = useTheme();
  void theme; // dep del tema: re-leer las CSS vars al cambiar claro/oscuro

  if (typeof document === 'undefined') return FALLBACK;

  const cs = getComputedStyle(document.documentElement);
  const token = (name: string, fb: string) => {
    const value = cs.getPropertyValue(name).trim();
    return value ? `oklch(${value})` : fb;
  };

  return {
    AL_DIA: token('--success', FALLBACK.AL_DIA),
    RIESGO_MEDIO: token('--warning', FALLBACK.RIESGO_MEDIO),
    RIESGO_ALTO: token('--destructive', FALLBACK.RIESGO_ALTO),
    SIN_ACTIVIDAD: token('--muted-foreground', FALLBACK.SIN_ACTIVIDAD),
  };
}
