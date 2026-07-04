import { apiClient } from '@/shared/services/api-client';
import { dispararDescarga } from '@/shared/services/download';
import type {
  CierreItemConfirmado,
  CierreItemSugerido,
  CierreRun,
  GenerarCierreInput,
} from '../types';

export const cierreCursadaService = {
  getItems: async (materiaId: number, cuatrimestreId: number): Promise<CierreItemSugerido[]> => {
    const { data } = await apiClient.get<CierreItemSugerido[]>(
      `/cierre-cursada/materias/${materiaId}/items`,
      { params: { cuatrimestre_id: cuatrimestreId } }
    );
    return data;
  },

  confirmarMapping: async (
    materiaId: number,
    cuatrimestreId: number,
    items: CierreItemConfirmado[]
  ): Promise<CierreItemSugerido[]> => {
    const { data } = await apiClient.post<CierreItemSugerido[]>(
      `/cierre-cursada/materias/${materiaId}/items`,
      { cuatrimestre_id: cuatrimestreId, items }
    );
    return data;
  },

  generar: async (materiaId: number, input: GenerarCierreInput): Promise<CierreRun> => {
    const { data } = await apiClient.post<CierreRun>(
      `/cierre-cursada/materias/${materiaId}/generar`,
      input
    );
    return data;
  },

  descargarExcel: async (runId: number): Promise<void> => {
    const resp = await apiClient.get(`/cierre-cursada/runs/${runId}/excel`, {
      responseType: 'blob',
    });
    dispararDescarga(resp, `cierre_cursada_${runId}.xlsx`);
  },

  getHistorial: async (materiaId: number): Promise<CierreRun[]> => {
    const { data } = await apiClient.get<{ runs: CierreRun[] }>(
      `/cierre-cursada/materias/${materiaId}/historial`
    );
    return data.runs;
  },
};
