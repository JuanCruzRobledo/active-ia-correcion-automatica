/**
 * Resumen legible de los errores de una corrección masiva por código (item #7).
 *
 * Traduce el mapa {error_code: count} (de GET /correcciones/global/progreso) a una línea
 * humana, ej: "5 límite de uso (rate limit) · 2 modelo sobrecargado · 1 otros".
 */
const ETIQUETAS: Record<string, string> = {
  GEMINI_RATE_LIMIT: 'límite de uso (rate limit)',
  GEMINI_OVERLOADED: 'modelo sobrecargado',
  GEMINI_API_KEY_INVALID: 'API Key inválida',
  SIN_CREDITOS: 'sin créditos',
  N8N_TIMEOUT: 'timeout del servicio de IA',
  N8N_ERROR: 'error del servicio de IA',
  IA_RESPUESTA_INVALIDA: 'respuesta inválida de la IA',
};

export function resumenErrores(
  erroresPorCodigo: Record<string, number> | undefined | null
): string {
  if (!erroresPorCodigo) return '';
  const partes = Object.entries(erroresPorCodigo)
    .filter(([, n]) => n > 0)
    .map(([code, n]) => `${n} ${ETIQUETAS[code] ?? 'otros'}`);
  return partes.join(' · ');
}
