// React Query hooks para Cohortes/Cuatrimestres
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { cohortesService } from '../services/cohortes.service';
import type { CohorteCreate, CohorteUpdate, CuatrimestreCreate } from '../types';

export const cohortesKeys = {
  all: ['cohortes'] as const,
};

export const useCohortes = () =>
  useQuery({
    queryKey: cohortesKeys.all,
    queryFn: cohortesService.getAll,
    staleTime: 5 * 60 * 1000,
  });

export const useCreateCohorte = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CohorteCreate) => cohortesService.create(data),
    onSuccess: () => {
      toast.success('Cohorte creada');
      qc.invalidateQueries({ queryKey: cohortesKeys.all });
    },
  });
};

export const useUpdateCohorte = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: CohorteUpdate }) =>
      cohortesService.update(id, data),
    onSuccess: () => {
      toast.success('Cohorte actualizada');
      qc.invalidateQueries({ queryKey: cohortesKeys.all });
    },
  });
};

export const useDeleteCohorte = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cohortesService.remove(id),
    onSuccess: () => {
      toast.success('Cohorte eliminada');
      qc.invalidateQueries({ queryKey: cohortesKeys.all });
    },
  });
};

export const useAddCuatrimestre = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ cohorteId, data }: { cohorteId: number; data: CuatrimestreCreate }) =>
      cohortesService.addCuatrimestre(cohorteId, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: cohortesKeys.all });
    },
  });
};

export const useDeleteCuatrimestre = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => cohortesService.removeCuatrimestre(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: cohortesKeys.all });
    },
  });
};
