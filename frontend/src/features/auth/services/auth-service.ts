/**
 * Authentication Service
 *
 * Handles all authentication operations:
 * - Login and logout
 * - Token management (localStorage)
 * - User session persistence
 * - Password change
 *
 * Ref: skills/react-typescript/SKILL.md
 * Ref: docs/specs/11-SEGURIDAD.md (JWT, localStorage)
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  LoginRequest,
  LoginResponse,
  LoginResult,
  ChangePasswordRequest,
  ChangePasswordResponse,
  UserInfo,
} from '@/shared/types';

// localStorage keys
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

/**
 * Evento custom disparado cada vez que se persiste una sesión nueva
 * (login, selección de universidad, switch de universidad).
 *
 * `localStorage` NO es reactivo dentro de la misma pestaña — el evento nativo
 * `storage` sólo dispara en OTRAS pestañas. `TenantProvider` (D1,
 * shared/context/TenantProvider.tsx) escucha este evento además de `storage`
 * para reflejar el cambio de sesión sin recargar la página.
 */
export const AUTH_SESSION_EVENT = 'auth-session-changed';

function persistirSesion(data: LoginResponse): void {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
}

/**
 * Login user with username and password.
 *
 * La respuesta es una unión discriminada por `requiere_seleccion`: cuando el
 * usuario tiene 2+ membresías activas, el backend NO manda `access_token` —
 * manda la lista de universidades disponibles y un `token_transicion` para el
 * segundo paso (ver `seleccionarUniversidad`). Sólo se persiste sesión en
 * `localStorage` cuando la respuesta trae `access_token`; la rama de
 * selección nunca toca `localStorage` (evita el bug histórico de guardar el
 * literal `"undefined"` en `auth_token`).
 *
 * @param credentials - Username and password
 * @returns LoginResult: token final o la respuesta intermedia de selección
 */
export async function login(credentials: LoginRequest): Promise<LoginResult> {
  const response = await apiClient.post<LoginResult>('/auth/login', credentials);
  const data = response.data;

  if ('requiere_seleccion' in data) {
    return data;
  }

  persistirSesion(data);
  return data;
}

/**
 * Segundo paso del login cuando `login()` devolvió `requiere_seleccion: true`.
 * Envía el `token_transicion` (como Bearer) y la universidad elegida; con el
 * token final recibido, persiste la sesión igual que un login directo.
 *
 * @param tokenTransicion - Token corto emitido por `/auth/login`
 * @param universidadId - Universidad elegida por el usuario
 * @returns LoginResponse con el token final
 */
export async function seleccionarUniversidad(
  tokenTransicion: string,
  universidadId: number
): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>(
    '/auth/select-universidad',
    { universidad_id: universidadId },
    { headers: { Authorization: `Bearer ${tokenTransicion}` } }
  );

  persistirSesion(response.data);
  return response.data;
}

/**
 * Cambia la universidad activa de una sesión ya autenticada (D1/D4/D6).
 *
 * A diferencia de `seleccionarUniversidad`, no usa un token de transición: el
 * usuario ya está logueado, así que el interceptor de axios adjunta el token
 * normal. `universidadId=null` es el modo global del superadmin ("Todas las
 * universidades") — el backend lo interpreta como sin filtro (Fase 4).
 *
 * @param universidadId - Universidad elegida, o `null` para modo global (sólo superadmin)
 * @returns LoginResponse con el token re-emitido
 */
export async function switchUniversidad(universidadId: number | null): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/switch-universidad', {
    universidad_id: universidadId,
  });

  persistirSesion(response.data);
  return response.data;
}

/**
 * Logout current user.
 * Clears token and user info from localStorage and redirects to login.
 */
export function logout(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);

  // Redirect to login page
  window.location.href = '/login';
}

/**
 * Get stored authentication token.
 *
 * @returns Token string or null if not found
 */
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/**
 * Get stored user info.
 *
 * @returns User info or null if not found
 */
export function getUser(): UserInfo | null {
  const userData = localStorage.getItem(USER_KEY);

  if (!userData) {
    return null;
  }

  try {
    return JSON.parse(userData) as UserInfo;
  } catch {
    // Invalid JSON in storage, clear it
    localStorage.removeItem(USER_KEY);
    return null;
  }
}

/**
 * Check if user is currently authenticated.
 * Verifies both token existence and token expiration.
 *
 * @returns True if authenticated, false otherwise
 */
export function isAuthenticated(): boolean {
  const token = getToken();

  if (!token) {
    return false;
  }

  // Decode JWT payload to check expiration
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    const isExpired = payload.exp * 1000 < Date.now();

    if (isExpired) {
      // Token expired, clear storage
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      return false;
    }

    return true;
  } catch {
    // Invalid token format
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    return false;
  }
}

/**
 * Change current user's password.
 *
 * @param data - Current password, new password, and confirmation
 * @returns Success message
 */
export async function changePassword(
  data: ChangePasswordRequest
): Promise<ChangePasswordResponse> {
  const response = await apiClient.post<ChangePasswordResponse>(
    '/auth/change-password',
    data
  );

  return response.data;
}

/**
 * Update stored user info.
 * Used after profile updates to keep localStorage in sync.
 *
 * @param user - Updated user info
 */
export function updateStoredUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/**
 * Mark the stored user's Gemini API key as invalid in localStorage.
 * Called when the backend returns a 402 (GEMINI_API_KEY_INVALID) error.
 * This updates localStorage immediately so the UI can show the warning banner.
 */
export function invalidateStoredApiKey(): void {
  const user = getUser();
  if (user) {
    user.gemini_api_key_valid = false;
    updateStoredUser(user);
  }
}

/**
 * Clear authentication data.
 * Similar to logout but without redirect (useful for testing or special cases).
 */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
