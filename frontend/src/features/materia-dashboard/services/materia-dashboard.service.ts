// Servicio de config de dashboard por materia (unidades + vinculación + auto-sugerencia)
import { apiClient } from '@/shared/services/api-client';
import type {
  MateriaDashboardConfig,
  MateriaDashboardConfigResponse,
  MoodleSeccionesSugeridas,
  Unidad,
  UnidadCreate,
} from '../types';

export const materiaDashboardService = {
  getUnidades: async (materiaId: number): Promise<Unidad[]> => {
    const { data } = await apiClient.get<Unidad[]>(`/materias/${materiaId}/unidades`);
    return data;
  },

  crearUnidad: async (materiaId: number, payload: UnidadCreate): Promise<Unidad> => {
    const { data } = await apiClient.post<Unidad>(
      `/materias/${materiaId}/unidades`,
      payload
    );
    return data;
  },

  eliminarUnidad: async (unidadId: number): Promise<void> => {
    await apiClient.delete(`/unidades/${unidadId}`);
  },

  getConfig: async (materiaId: number): Promise<MateriaDashboardConfigResponse> => {
    const { data } = await apiClient.get<MateriaDashboardConfigResponse>(
      `/materias/${materiaId}/dashboard-config`
    );
    return data;
  },

  setConfig: async (
    materiaId: number,
    payload: MateriaDashboardConfig
  ): Promise<MateriaDashboardConfigResponse> => {
    const { data } = await apiClient.put<MateriaDashboardConfigResponse>(
      `/materias/${materiaId}/dashboard-config`,
      payload
    );
    return data;
  },

  getMoodleSecciones: async (materiaId: number): Promise<MoodleSeccionesSugeridas> => {
    const { data } = await apiClient.get<MoodleSeccionesSugeridas>(
      `/materias/${materiaId}/moodle-secciones`
    );
    return data;
  },

  /** Reemplaza las unidades de la materia por las secciones tildadas (el orden define el número). */
  sincronizarUnidades: async (
    materiaId: number,
    secciones: { moodle_section_id: number; nombre?: string | null }[]
  ): Promise<Unidad[]> => {
    const { data } = await apiClient.put<Unidad[]>(
      `/materias/${materiaId}/unidades/sync`,
      { secciones }
    );
    return data;
  },
};
