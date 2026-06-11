// Servicio del ABM de Tutores Nexo
import { apiClient } from '@/shared/services/api-client';
import type { TutorNexo, TutorNexoCreate, TutorNexoUpdate } from '../types';

export const tutoresNexoService = {
  getAll: async (): Promise<TutorNexo[]> => {
    const { data } = await apiClient.get<TutorNexo[]>('/tutores-nexo/');
    return data;
  },

  create: async (payload: TutorNexoCreate): Promise<TutorNexo> => {
    const { data } = await apiClient.post<TutorNexo>('/tutores-nexo/', payload);
    return data;
  },

  update: async (id: number, payload: TutorNexoUpdate): Promise<TutorNexo> => {
    const { data } = await apiClient.put<TutorNexo>(`/tutores-nexo/${id}`, payload);
    return data;
  },

  remove: async (id: number): Promise<void> => {
    await apiClient.delete(`/tutores-nexo/${id}`);
  },
};
