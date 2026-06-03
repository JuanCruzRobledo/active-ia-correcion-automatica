// React Query hooks del dashboard de gestores
import { useMutation, useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { dashboardGestorService } from '../services/dashboard-gestor.service';
import type { EstadoAvance } from '../types';

export const dashboardGestorKeys = {
  arbol: ['dashboard-gestor', 'arbol'] as const,
  avance: (cuatrimestreId: number | null, materiaId: number | null) =>
    ['dashboard-gestor', 'avance', cuatrimestreId, materiaId] as const,
  detalle: (cuatrimestreId: number | null, estado: EstadoAvance | null, materiaId: number | null) =>
    ['dashboard-gestor', 'detalle', cuatrimestreId, estado, materiaId] as const,
};

export const useArbol = () =>
  useQuery({
    queryKey: dashboardGestorKeys.arbol,
    queryFn: dashboardGestorService.getArbol,
    staleTime: 5 * 60 * 1000,
  });

export const useAvance = (cuatrimestreId: number | null, materiaId: number | null) =>
  useQuery({
    queryKey: dashboardGestorKeys.avance(cuatrimestreId, materiaId),
    queryFn: () => dashboardGestorService.getAvance(cuatrimestreId as number, materiaId),
    enabled: cuatrimestreId != null,
  });

export const useDetalle = (
  cuatrimestreId: number | null,
  estado: EstadoAvance | null,
  materiaId: number | null
) =>
  useQuery({
    queryKey: dashboardGestorKeys.detalle(cuatrimestreId, estado, materiaId),
    queryFn: () =>
      dashboardGestorService.getDetalle(cuatrimestreId as number, estado as EstadoAvance, materiaId),
    enabled: cuatrimestreId != null && estado != null,
  });

export const useDescargarExcel = () =>
  useMutation({
    mutationFn: ({
      cuatrimestreId,
      materiaId,
    }: {
      cuatrimestreId: number;
      materiaId: number | null;
    }) => dashboardGestorService.descargarExcel(cuatrimestreId, materiaId),
    onError: () => toast.error('No se pudo generar el Excel'),
  });
