// Servicio de lectura del dashboard de gestores
import { apiClient } from '@/shared/services/api-client';
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
    const dispo = resp.headers['content-disposition'] as string | undefined;
    const match = dispo ? /filename="?([^"]+)"?/.exec(dispo) : null;
    const filename = match?.[1] ?? 'avance.xlsx';

    const url = URL.createObjectURL(resp.data as Blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
