import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { cierreCursadaService } from '../services/cierre-cursada.service';
import type { CierreItemConfirmado, GenerarCierreInput } from '../types';

export const cierreCursadaKeys = {
  items: (materiaId: number, cuatrimestreId: number) =>
    ['cierre-cursada', 'items', materiaId, cuatrimestreId] as const,
  historial: (materiaId: number) => ['cierre-cursada', 'historial', materiaId] as const,
};

export const useCierreItems = (materiaId: number, cuatrimestreId: number) =>
  useQuery({
    queryKey: cierreCursadaKeys.items(materiaId, cuatrimestreId),
    queryFn: () => cierreCursadaService.getItems(materiaId, cuatrimestreId),
    enabled: !!materiaId && !!cuatrimestreId,
  });

export const useConfirmarMapping = (materiaId: number, cuatrimestreId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (items: CierreItemConfirmado[]) =>
      cierreCursadaService.confirmarMapping(materiaId, cuatrimestreId, items),
    onSuccess: () => {
      toast.success('Mapeo de ítems confirmado');
      qc.invalidateQueries({ queryKey: cierreCursadaKeys.items(materiaId, cuatrimestreId) });
    },
  });
};

export const useGenerarCierre = (materiaId: number) => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: GenerarCierreInput) => cierreCursadaService.generar(materiaId, input),
    onSuccess: () => {
      toast.success('Cierre de cursada generado');
      qc.invalidateQueries({ queryKey: cierreCursadaKeys.historial(materiaId) });
    },
  });
};

export const useHistorialCierre = (materiaId: number) =>
  useQuery({
    queryKey: cierreCursadaKeys.historial(materiaId),
    queryFn: () => cierreCursadaService.getHistorial(materiaId),
    enabled: !!materiaId,
  });
