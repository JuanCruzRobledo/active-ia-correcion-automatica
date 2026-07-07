import { apiClient } from '@/shared/services/api-client';
import { dispararDescarga } from '@/shared/services/download';
import type { CierreRun, GenerarCierreInput } from '../types';

export const cierreCursadaService = {
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
