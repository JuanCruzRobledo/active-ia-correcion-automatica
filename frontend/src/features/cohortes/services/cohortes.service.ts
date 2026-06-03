// Servicio de Cohortes/Cuatrimestres
import { apiClient } from '@/shared/services/api-client';
import type {
  Cohorte,
  CohorteCreate,
  CohorteUpdate,
  Cuatrimestre,
  CuatrimestreCreate,
} from '../types';

export const cohortesService = {
  getAll: async (): Promise<Cohorte[]> => {
    const { data } = await apiClient.get<Cohorte[]>('/cohortes/');
    return data;
  },

  create: async (payload: CohorteCreate): Promise<Cohorte> => {
    const { data } = await apiClient.post<Cohorte>('/cohortes/', payload);
    return data;
  },

  update: async (id: number, payload: CohorteUpdate): Promise<Cohorte> => {
    const { data } = await apiClient.put<Cohorte>(`/cohortes/${id}`, payload);
    return data;
  },

  remove: async (id: number): Promise<void> => {
    await apiClient.delete(`/cohortes/${id}`);
  },

  addCuatrimestre: async (
    cohorteId: number,
    payload: CuatrimestreCreate
  ): Promise<Cuatrimestre> => {
    const { data } = await apiClient.post<Cuatrimestre>(
      `/cohortes/${cohorteId}/cuatrimestres`,
      payload
    );
    return data;
  },

  removeCuatrimestre: async (cuatrimestreId: number): Promise<void> => {
    await apiClient.delete(`/cohortes/cuatrimestres/${cuatrimestreId}`);
  },
};
