/**
 * fetch autenticado hacia la API (ARCH-011).
 *
 * Los flujos SSE/streaming (importar Moodle, entregar todo, snapshots, previews de
 * notificaciones) usan `fetch` en vez del `apiClient` de axios porque axios no
 * streamea bien el body. El costo era que cada service reimplementaba a mano la
 * baseURL, la lectura del JWT de localStorage y el header Authorization. Este helper
 * centraliza ESO en un solo lugar (equivalente al request-interceptor de axios).
 *
 * `path` es relativo a la baseURL del apiClient (ej: '/moodle/importar/stream').
 * Preserva el comportamiento previo: si no hay token, NO se manda Authorization;
 * los headers de `init` (p. ej. Content-Type) se combinan con el de auth.
 */
import { apiClient } from './api-client';

const TOKEN_KEY = 'auth_token';

export function fetchWithAuth(path: string, init: RequestInit = {}): Promise<Response> {
  const baseURL = apiClient.defaults.baseURL ?? '/api/v1';
  const token = localStorage.getItem(TOKEN_KEY);

  const headers = new Headers(init.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(`${baseURL}${path}`, { ...init, headers });
}
