/**
 * Extracción unificada del mensaje de error del backend (ERR-005).
 *
 * El backend responde el `detail` de un error HTTP en TRES formas distintas:
 *  - string simple                 → "No tenés permisos."
 *  - array de errores de validación → Pydantic/FastAPI 422 ([{ msg }, ...])
 *  - objeto { error_code, message } → errores de IA "ricos" (402 key inválida,
 *                                     402 sin créditos, 429 rate limit,
 *                                     503 sobrecargado; ver correccion_service.py)
 *
 * Antes cada capa (interceptor axios, getErrorMessage compartido, hooks) parseaba
 * su propio subconjunto, y la forma objeto se perdía en varias rutas. Este módulo
 * centraliza el parseo para que todas usen la MISMA lógica.
 */

/** Forma "rica" del detail para errores de IA provider-aware. */
export interface ApiErrorObjectDetail {
  error_code?: string;
  message?: string;
}

/** Item de la lista de errores de validación de Pydantic/FastAPI. */
export interface ApiErrorArrayItem {
  msg?: string;
}

/** Todas las formas que puede tener `detail` en una respuesta de error. */
export type ApiErrorDetailShape =
  | string
  | ApiErrorArrayItem[]
  | ApiErrorObjectDetail
  | null
  | undefined;

/**
 * Extrae un mensaje legible del `detail` de un error del backend, contemplando
 * las tres formas (string, array de validación, objeto { error_code, message }).
 *
 * Devuelve `undefined` cuando no hay un mensaje utilizable, para que el caller
 * aplique su propio fallback en vez de mostrar un texto vacío o técnico.
 */
export function extractDetailMessage(detail: ApiErrorDetailShape): string | undefined {
  if (!detail) return undefined;

  if (typeof detail === 'string') {
    return detail || undefined;
  }

  if (Array.isArray(detail)) {
    const msgs = detail
      .map((e) => e?.msg)
      .filter((m): m is string => typeof m === 'string' && m.length > 0);
    return msgs.length > 0 ? msgs.join('; ') : undefined;
  }

  if (typeof detail.message === 'string' && detail.message.length > 0) {
    return detail.message;
  }

  return undefined;
}
