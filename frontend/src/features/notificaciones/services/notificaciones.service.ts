// Servicio de notificaciones por email (config, disparo, prueba, historial, preview)
import { apiClient } from '@/shared/services/api-client';
import { fetchWithAuth } from '@/shared/services/fetchWithAuth';
import type {
  CorridaResumen,
  EnvioEmailLog,
  NotifCronConfig,
  NotifCronConfigUpdate,
} from '../types';

export const notificacionesService = {
  getConfig: async (): Promise<NotifCronConfig> => {
    const { data } = await apiClient.get<NotifCronConfig>('/notificaciones/cron-config');
    return data;
  },

  setConfig: async (payload: NotifCronConfigUpdate): Promise<NotifCronConfig> => {
    const { data } = await apiClient.put<NotifCronConfig>(
      '/notificaciones/cron-config',
      payload
    );
    return data;
  },

  dispararCorrida: async (opts: {
    refrescar: boolean;
    incluirAlumnos: boolean;
    incluirNexos: boolean;
    comisiones: string[];
  }): Promise<CorridaResumen> => {
    const params = new URLSearchParams();
    params.set('refrescar', String(opts.refrescar));
    params.set('incluir_alumnos', String(opts.incluirAlumnos));
    params.set('incluir_nexos', String(opts.incluirNexos));
    opts.comisiones.forEach((c) => params.append('comisiones', c));
    const { data } = await apiClient.post<CorridaResumen>(
      `/notificaciones/disparar?${params.toString()}`
    );
    return data;
  },

  enviarPrueba: async (email: string): Promise<EnvioEmailLog> => {
    const { data } = await apiClient.post<EnvioEmailLog>('/notificaciones/enviar-prueba', {
      email,
    });
    return data;
  },

  getHistorial: async (): Promise<EnvioEmailLog[]> => {
    const { data } = await apiClient.get<EnvioEmailLog[]>('/notificaciones/historial');
    return data;
  },
};

/** Abre en una pestaña nueva la muestra (HTML/PDF/Excel) del tipo indicado, con auth. */
export async function abrirPreview(tipo: 'alumno' | 'tutor' | 'nexo'): Promise<void> {
  const resp = await fetchWithAuth(`/notificaciones/preview/${tipo}`);
  if (!resp.ok) throw new Error(`Error ${resp.status} al generar la vista previa`);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank');
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
