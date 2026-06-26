// features/perfil/types/index.ts
/**
 * Types for user profile feature.
 * Based on backend schemas and specs/03-REQUISITOS-FUNCIONALES.md
 */

/**
 * Modo de corrección elegido por el usuario.
 * - 'gemini'     → Corrección Gemini Studio (Google, key directa).
 * - 'openrouter' → Corrección OpenRouter (beta), modelo google/gemini-3.5-flash.
 */
export type CorrectionProvider = 'gemini' | 'openrouter';

/**
 * User profile information (extended from User).
 */
export interface UserProfile {
  id: number;
  username: string;
  nombre: string;
  email: string | null;
  rol: string;
  primer_login: boolean;
  gemini_api_key_valid: boolean;
  gemini_api_key_last_4: string | null;
  gemini_api_key_paga: boolean;
  // Modo de corrección activo + estado de la key de OpenRouter (separada de la de Gemini).
  correction_provider: CorrectionProvider;
  openrouter_api_key_valid: boolean;
  openrouter_api_key_last_4: string | null;
  moodle_username: string | null;
  moodle_host: string | null;
  moodle_configured: boolean;
  activo: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

/**
 * Request to update an API Key for a given provider.
 */
export interface UpdateApiKeyRequest {
  gemini_api_key: string;
  provider: CorrectionProvider;
}

/**
 * Response after updating API Key.
 */
export interface UpdateApiKeyResponse {
  message: string;
  valid: boolean;
}

export interface MoodleCredentialsRequest {
  moodle_host: string;
  moodle_username: string;
  moodle_password: string;
}

export interface MoodleCredentialsResponse {
  moodle_username: string;
  moodle_host: string;
  configured: boolean;
}
