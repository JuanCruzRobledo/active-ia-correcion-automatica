// Servicio de config del cron de snapshots + disparo manual
import { apiClient } from '@/shared/services/api-client';
import { fetchWithAuth } from '@/shared/services/fetchWithAuth';
import type {
  CronConfig,
  CronConfigUpdate,
  MateriaConfigurada,
  SnapshotResumen,
} from '../types';

export const cronConfigService = {
  getConfig: async (): Promise<CronConfig> => {
    const { data } = await apiClient.get<CronConfig>('/gestion/dashboard/cron-config');
    return data;
  },

  setConfig: async (payload: CronConfigUpdate): Promise<CronConfig> => {
    const { data } = await apiClient.put<CronConfig>(
      '/gestion/dashboard/cron-config',
      payload
    );
    return data;
  },

  getMateriasConfiguradas: async (): Promise<MateriaConfigurada[]> => {
    const { data } = await apiClient.get<MateriaConfigurada[]>(
      '/gestion/dashboard/materias-configuradas'
    );
    return data;
  },

  /** Dispara el snapshot a mano (todas las materias configuradas si no se pasa materia_id). */
  dispararSnapshot: async (materiaId?: number): Promise<SnapshotResumen[]> => {
    const url =
      materiaId != null
        ? `/gestion/dashboard/snapshot?materia_id=${materiaId}`
        : '/gestion/dashboard/snapshot';
    const { data } = await apiClient.post<SnapshotResumen[]>(url);
    return data;
  },
};

export interface ProgresoEvento {
  tipo: 'progreso' | 'done' | 'error';
  materia_id?: number;
  materia_idx?: number;
  materias_total?: number;
  procesados?: number;
  total?: number;
  materias?: number;
  detalle?: string;
}

/**
 * Dispara el snapshot consumiendo el stream SSE de progreso. Usa fetch (no
 * EventSource) para poder mandar el header Authorization, vía el helper compartido
 * fetchWithAuth. Llama onEvent por cada evento (progreso por alumno, done, error).
 */
export async function dispararSnapshotStream(
  materiaIds: number[],
  onEvent: (e: ProgresoEvento) => void,
  signal?: AbortSignal
): Promise<void> {
  const qs = materiaIds.map((id) => `materia_ids=${id}`).join('&');
  const path = `/gestion/dashboard/snapshot/stream${qs ? `?${qs}` : ''}`;

  const resp = await fetchWithAuth(path, { signal });
  if (!resp.ok || !resp.body) {
    throw new Error(`Error ${resp.status} al iniciar el snapshot`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith('data:')) {
        const payload = line.slice(5).trim();
        if (payload) onEvent(JSON.parse(payload) as ProgresoEvento);
      }
    }
  }
}
