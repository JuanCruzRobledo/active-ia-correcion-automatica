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
