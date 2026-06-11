// Servicio de config de dashboard por materia (unidades + vinculación + auto-sugerencia)
import { apiClient } from '@/shared/services/api-client';
import type {
  ExamenInput,
  ExamenMateria,
  MateriaDashboardConfig,
  MateriaDashboardConfigResponse,
  MoodleActividad,
  MoodleSeccionesSugeridas,
  Unidad,
  UnidadComponentes,
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

  /** Actividades de Moodle de una unidad (trackeables + evaluables), para elegir componentes. */
  getActividadesUnidad: async (unidadId: number): Promise<MoodleActividad[]> => {
    const { data } = await apiClient.get<MoodleActividad[]>(
      `/unidades/${unidadId}/actividades`
    );
    return data;
  },

  /** Reemplaza el set de componentes (tipo + cmid + fuente) de una unidad. */
  setComponentesUnidad: async (
    unidadId: number,
    payload: UnidadComponentes
  ): Promise<Unidad> => {
    const { data } = await apiClient.put<Unidad>(
      `/unidades/${unidadId}/componentes`,
      payload
    );
    return data;
  },

  // ===================== Exámenes de la materia =====================

  getExamenes: async (materiaId: number): Promise<ExamenMateria[]> => {
    const { data } = await apiClient.get<ExamenMateria[]>(
      `/materias/${materiaId}/examenes`
    );
    return data;
  },

  crearExamen: async (
    materiaId: number,
    payload: ExamenInput
  ): Promise<ExamenMateria> => {
    const { data } = await apiClient.post<ExamenMateria>(
      `/materias/${materiaId}/examenes`,
      payload
    );
    return data;
  },

  actualizarExamen: async (
    examenId: number,
    payload: ExamenInput
  ): Promise<ExamenMateria> => {
    const { data } = await apiClient.put<ExamenMateria>(
      `/examenes/${examenId}`,
      payload
    );
    return data;
  },

  eliminarExamen: async (examenId: number): Promise<void> => {
    await apiClient.delete(`/examenes/${examenId}`);
  },
};
