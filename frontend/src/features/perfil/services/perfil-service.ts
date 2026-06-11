// features/perfil/services/perfil-service.ts
/**
 * Service layer for user profile operations.
 *
 * Handles profile retrieval and API Key management.
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md HU-PERF-01
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  UserProfile,
  UpdateApiKeyRequest,
  UpdateApiKeyResponse,
  MoodleCredentialsRequest,
  MoodleCredentialsResponse,
} from '../types';

/**
 * Get current user's profile.
 *
 * @returns User profile with complete information
 */
export async function getProfile(): Promise<UserProfile> {
  const { data } = await apiClient.get<UserProfile>('/perfil');
  return data;
}

/**
 * Update user's Gemini API Key.
 * Backend validates format and performs test call to Gemini.
 *
 * @param apiKey - Gemini API Key (must start with "AIza")
 * @returns Validation result
 */
export async function updateApiKey(
  apiKey: string
): Promise<UpdateApiKeyResponse> {
  const { data } = await apiClient.post<UpdateApiKeyResponse>(
    '/perfil/api-key',
    { gemini_api_key: apiKey } as UpdateApiKeyRequest
  );
  return data;
}

export async function updateMoodleCredentials(
  credentials: MoodleCredentialsRequest
): Promise<MoodleCredentialsResponse> {
  const { data } = await apiClient.patch<MoodleCredentialsResponse>(
    '/usuarios/me/moodle-credentials',
    credentials
  );
  return data;
}

/**
 * Setea (o limpia con null) el email de notificaciones del usuario actual.
 */
export async function updateEmail(
  email: string | null
): Promise<{ message: string; email: string | null }> {
  const { data } = await apiClient.patch<{ message: string; email: string | null }>(
    '/perfil/email',
    { email }
  );
  return data;
}

/**
 * Marca/desmarca la API key como paga (toggle manual). Habilita 'Corregir todo'.
 */
export async function updateKeyPaga(
  paga: boolean
): Promise<{ message: string; gemini_api_key_paga: boolean }> {
  const { data } = await apiClient.patch<{
    message: string;
    gemini_api_key_paga: boolean;
  }>('/perfil/key-paga', { paga });
  return data;
}
