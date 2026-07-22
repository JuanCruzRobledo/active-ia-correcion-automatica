// React Query hooks de notificaciones por email
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import toast from 'react-hot-toast';
import { extractDetailMessage } from '@/shared/utils/apiError';
import { notificacionesService } from '../services/notificaciones.service';
import type { NotifCronConfigUpdate } from '../types';

/** Mensaje legible del backend, con fallback (para los onError de las mutaciones). */
function mensajeError(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    return extractDetailMessage(error.response?.data?.detail) ?? fallback;
  }
  return fallback;
}

export const notificacionesKeys = {
  config: ['notificaciones', 'cron-config'] as const,
  historial: ['notificaciones', 'historial'] as const,
};

export const useNotifConfig = () =>
  useQuery({
    queryKey: notificacionesKeys.config,
    queryFn: notificacionesService.getConfig,
    staleTime: 60 * 1000,
  });

export const useSetNotifConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: NotifCronConfigUpdate) => notificacionesService.setConfig(data),
    onSuccess: () => {
      toast.success('Configuración guardada');
      qc.invalidateQueries({ queryKey: notificacionesKeys.config });
    },
    onError: (error) => {
      toast.error(mensajeError(error, 'No se pudo guardar la configuración. Intentá nuevamente.'));
    },
  });
};

export const useHistorialNotif = () =>
  useQuery({
    queryKey: notificacionesKeys.historial,
    queryFn: notificacionesService.getHistorial,
    staleTime: 15 * 1000,
  });

export const useDispararCorrida = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (opts: {
      refrescar: boolean;
      incluirAlumnos: boolean;
      incluirNexos: boolean;
      comisiones: string[];
    }) => notificacionesService.dispararCorrida(opts),
    onSuccess: (r) => {
      toast.success(
        `Corrida lista: ${r.alumnos} alumnos · ${r.tutores} tutores · ${r.nexos} nexos`
      );
      qc.invalidateQueries({ queryKey: notificacionesKeys.historial });
    },
    onError: (error) => {
      toast.error(
        mensajeError(
          error,
          'No se pudo disparar la corrida de emails. Revisá la conexión e intentá de nuevo.'
        )
      );
    },
  });
};

export const useEnviarPrueba = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (email: string) => notificacionesService.enviarPrueba(email),
    onSuccess: (log) => {
      if (log.estado === 'ENVIADO') {
        toast.success('Email de prueba enviado');
      } else {
        toast.error(`No se pudo enviar: ${log.error ?? log.estado}`);
      }
      qc.invalidateQueries({ queryKey: notificacionesKeys.historial });
    },
  });
};
