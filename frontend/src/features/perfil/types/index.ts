// features/perfil/types/index.ts
/**
 * Types for user profile feature.
 * Based on backend schemas and specs/03-REQUISITOS-FUNCIONALES.md
 */

/**
 * User profile information (extended from User).
 */
export interface UserProfile {
  id: number;
  username: string;
  nombre: string;
  rol: string;
  primer_login: boolean;
  gemini_api_key_valid: boolean;
  gemini_api_key_last_4: string | null;
  moodle_username: string | null;
  moodle_host: string | null;
  moodle_configured: boolean;
  activo: boolean;
  created_at: string;
  updated_at: string;
  last_login: string | null;
}

/**
 * Request to update Gemini API Key.
 */
export interface UpdateApiKeyRequest {
  gemini_api_key: string;
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
