// React Query hooks para Tutores Nexo
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { tutoresNexoService } from '../services/tutores-nexo.service';
import type { TutorNexoCreate, TutorNexoUpdate } from '../types';

export const tutoresNexoKeys = {
  all: ['tutores-nexo'] as const,
};

export const useTutoresNexo = () =>
  useQuery({
    queryKey: tutoresNexoKeys.all,
    queryFn: tutoresNexoService.getAll,
    staleTime: 5 * 60 * 1000,
  });

export const useCreateTutorNexo = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TutorNexoCreate) => tutoresNexoService.create(data),
    onSuccess: () => {
      toast.success('Tutor nexo creado');
      qc.invalidateQueries({ queryKey: tutoresNexoKeys.all });
    },
  });
};

export const useUpdateTutorNexo = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: TutorNexoUpdate }) =>
      tutoresNexoService.update(id, data),
    onSuccess: () => {
      toast.success('Tutor nexo actualizado');
      qc.invalidateQueries({ queryKey: tutoresNexoKeys.all });
    },
  });
};

export const useDeleteTutorNexo = () => {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => tutoresNexoService.remove(id),
    onSuccess: () => {
      toast.success('Tutor nexo eliminado');
      qc.invalidateQueries({ queryKey: tutoresNexoKeys.all });
    },
  });
};
