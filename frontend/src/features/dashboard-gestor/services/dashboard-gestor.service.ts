// Servicio de lectura del dashboard de gestores
import { apiClient } from '@/shared/services/api-client';
import { dispararDescarga } from '@/shared/services/download';
import type { AlumnoDetalle, AvanceResponse, CohorteArbol, EstadoAvance } from '../types';

export const dashboardGestorService = {
  getArbol: async (): Promise<CohorteArbol[]> => {
    const { data } = await apiClient.get<CohorteArbol[]>('/gestion/dashboard/arbol');
    return data;
  },

  getAvance: async (
    cuatrimestreId: number,
    materiaId?: number | null
  ): Promise<AvanceResponse> => {
    const params = new URLSearchParams({ cuatrimestre_id: String(cuatrimestreId) });
    if (materiaId != null) params.append('materia_id', String(materiaId));
    const { data } = await apiClient.get<AvanceResponse>(
      `/gestion/dashboard/avance?${params.toString()}`
    );
    return data;
  },

  getDetalle: async (
    cuatrimestreId: number,
    estado: EstadoAvance,
    materiaId?: number | null
  ): Promise<AlumnoDetalle[]> => {
    const params = new URLSearchParams({
      cuatrimestre_id: String(cuatrimestreId),
      estado,
    });
    if (materiaId != null) params.append('materia_id', String(materiaId));
    const { data } = await apiClient.get<AlumnoDetalle[]>(
      `/gestion/dashboard/avance/detalle?${params.toString()}`
    );
    return data;
  },

  descargarExcel: async (
    cuatrimestreId: number,
    materiaId?: number | null
  ): Promise<void> => {
    const params = new URLSearchParams({ cuatrimestre_id: String(cuatrimestreId) });
    if (materiaId != null) params.append('materia_id', String(materiaId));
    const resp = await apiClient.get(
      `/gestion/dashboard/avance/excel?${params.toString()}`,
      { responseType: 'blob' }
    );
    dispararDescarga(resp, 'avance.xlsx');
  },
};
