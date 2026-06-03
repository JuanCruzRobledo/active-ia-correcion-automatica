// React Query hooks para la config del cron + disparo manual
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { cronConfigService } from '../services/cron-config.service';
import type { CronConfigUpdate } from '../types';

export const cronConfigKeys = {
  config: ['cron-config'] as const,
  materiasConfiguradas: ['cron-config', 'materias-configuradas'] as const,
};

export const useCronConfig = () =>
  useQuery({
    queryKey: cronConfigKeys.config,
    queryFn: cronConfigService.getConfig,
    staleTime: 60 * 1000,
  });

export const useMateriasConfiguradas = () =>
  useQuery({
    queryKey: cronConfigKeys.materiasConfiguradas,
    queryFn: cronConfigService.getMateriasConfiguradas,
    staleTime: 30 * 1000,
  });

export const useSetCronConfig = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CronConfigUpdate) => cronConfigService.setConfig(data),
    onSuccess: () => {
      toast.success('Configuración del cron guardada');
      qc.invalidateQueries({ queryKey: cronConfigKeys.config });
    },
  });
};

export const useDispararSnapshot = () =>
  useMutation({
    mutationFn: (materiaId?: number) => cronConfigService.dispararSnapshot(materiaId),
    onSuccess: (snapshots) => {
      toast.success(`Snapshot generado: ${snapshots.length} materia(s)`);
    },
  });
