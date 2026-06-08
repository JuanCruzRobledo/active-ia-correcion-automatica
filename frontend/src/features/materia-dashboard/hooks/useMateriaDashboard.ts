// React Query hooks para la config de dashboard por materia
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { materiaDashboardService } from '../services/materia-dashboard.service';
import type { MateriaDashboardConfig, UnidadComponentes, UnidadCreate } from '../types';

export const materiaDashboardKeys = {
  unidades: (materiaId: number) => ['materia-dashboard', 'unidades', materiaId] as const,
  config: (materiaId: number) => ['materia-dashboard', 'config', materiaId] as const,
};

export const useUnidades = (materiaId: number) =>
  useQuery({
    queryKey: materiaDashboardKeys.unidades(materiaId),
    queryFn: () => materiaDashboardService.getUnidades(materiaId),
    enabled: !!materiaId,
  });

export const useDashboardConfig = (materiaId: number) =>
  useQuery({
    queryKey: materiaDashboardKeys.config(materiaId),
    queryFn: () => materiaDashboardService.getConfig(materiaId),
    enabled: !!materiaId,
  });

export const useSetDashboardConfig = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MateriaDashboardConfig) =>
      materiaDashboardService.setConfig(materiaId, data),
    onSuccess: () => {
      toast.success('Configuración guardada');
      qc.invalidateQueries({ queryKey: materiaDashboardKeys.config(materiaId) });
    },
  });
};

export const useCrearUnidad = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: UnidadCreate) =>
      materiaDashboardService.crearUnidad(materiaId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: materiaDashboardKeys.unidades(materiaId) });
    },
  });
};

export const useEliminarUnidad = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (unidadId: number) => materiaDashboardService.eliminarUnidad(unidadId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: materiaDashboardKeys.unidades(materiaId) });
    },
  });
};

/** Trae secciones de Moodle bajo demanda (botón "Detectar"). */
export const useDetectarSecciones = (materiaId: number) =>
  useMutation({
    mutationFn: () => materiaDashboardService.getMoodleSecciones(materiaId),
  });

export const useSincronizarUnidades = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (secciones: { moodle_section_id: number; nombre?: string | null }[]) =>
      materiaDashboardService.sincronizarUnidades(materiaId, secciones),
    onSuccess: () => {
      toast.success('Unidades guardadas');
      qc.invalidateQueries({ queryKey: materiaDashboardKeys.unidades(materiaId) });
    },
  });
};

/** Actividades de Moodle de una unidad (bajo demanda, al expandir su config). */
export const useActividadesUnidad = (unidadId: number, enabled: boolean) =>
  useQuery({
    queryKey: ['materia-dashboard', 'actividades-unidad', unidadId] as const,
    queryFn: () => materiaDashboardService.getActividadesUnidad(unidadId),
    enabled: enabled && !!unidadId,
    staleTime: 5 * 60 * 1000,
  });

export const useSetComponentesUnidad = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ unidadId, data }: { unidadId: number; data: UnidadComponentes }) =>
      materiaDashboardService.setComponentesUnidad(unidadId, data),
    onSuccess: () => {
      toast.success('Componentes de la unidad guardados');
      qc.invalidateQueries({ queryKey: materiaDashboardKeys.unidades(materiaId) });
    },
  });
};
