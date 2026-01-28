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
  ChangePasswordRequest,
  ChangePasswordResponse,
  UserInfo,
} from '@/shared/types';

// localStorage keys
const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

/**
 * Login user with username and password.
 * Stores token and user info in localStorage.
 *
 * @param credentials - Username and password
 * @returns Login response with token and user info
 */
export async function login(credentials: LoginRequest): Promise<LoginResponse> {
  const response = await apiClient.post<LoginResponse>('/auth/login', credentials);

  const { access_token, user } = response.data;

  // Store token and user info
  localStorage.setItem(TOKEN_KEY, access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));

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
 * Clear authentication data.
 * Similar to logout but without redirect (useful for testing or special cases).
 */
export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}
