/**
 * Endpoints de autenticación cuyo 401 significa "credenciales inválidas" o
 * "cambio de contraseña rechazado" — NO "sesión expirada".
 *
 * El interceptor global de axios (`api-client.ts`) usa `isAuthEndpoint` para
 * decidir, ante un 401, si debe limpiar la sesión y redirigir a /login (token
 * expirado en un endpoint autenticado) o dejar pasar el error tal cual para que
 * el caller muestre el mensaje real del backend (login / cambio de contraseña).
 *
 * Criterio para agregar rutas acá: sumá un endpoint SÓLO si su 401 representa un
 * fallo de credenciales que el usuario debe ver, y NO una sesión expirada que
 * deba forzar logout + redirect.
 */
export const AUTH_ENDPOINTS = ['/auth/login', '/auth/change-password'] as const;

/**
 * Devuelve `true` si la URL corresponde a un endpoint de autenticación cuyo 401
 * NO debe tratarse como sesión expirada.
 *
 * @param url URL relativa de la request (`error.config?.url`), o `undefined`.
 */
export function isAuthEndpoint(url: string | undefined): boolean {
  if (!url) {
    return false;
  }
  return AUTH_ENDPOINTS.some((endpoint) => url.includes(endpoint));
}
