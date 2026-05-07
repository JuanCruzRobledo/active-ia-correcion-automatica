import { apiClient } from '@/shared/services/api-client';
import type { MateriasPendientesResponse } from '../types';

export async function getPendientesMoodle(): Promise<MateriasPendientesResponse> {
  const { data } = await apiClient.get<MateriasPendientesResponse>('/pendientes/moodle');
  return data;
}
