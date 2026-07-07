import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { cierreCursadaService } from '../services/cierre-cursada.service';
import type { GenerarCierreInput } from '../types';

export const cierreCursadaKeys = {
  historial: (materiaId: number) => ['cierre-cursada', 'historial', materiaId] as const,
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
