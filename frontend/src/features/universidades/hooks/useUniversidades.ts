// features/universidades/hooks/useUniversidades.ts
/**
 * React Query hooks for the universidades feature (Fase 5 multi-tenant).
 *
 * `useUniversidadesMias` alimenta el selector (D5); el resto son los hooks
 * del ABM de superadmin (Parte 4), con invalidación del listado tras cada
 * mutación.
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { universidadesService } from '../services/universidades-service';
import type {
  Universidad,
  UniversidadCreate,
  UniversidadList,
  UniversidadPropia,
  UniversidadUpdate,
  UniversidadesFilters,
} from '../types';

export const universidadesKeys = {
  all: ['universidades'] as const,
  mias: () => [...universidadesKeys.all, 'mias'] as const,
  list: (filters: UniversidadesFilters) => [...universidadesKeys.all, 'list', filters] as const,
};

/** Universidades del usuario autenticado, para el selector de tenant. */
export const useUniversidadesMias = () => {
  return useQuery<UniversidadPropia[], Error>({
    queryKey: universidadesKeys.mias(),
    queryFn: () => universidadesService.getMias(),
    staleTime: 5 * 60 * 1000,
  });
};

/** Listado paginado del ABM de superadmin. */
export const useUniversidades = (filters: UniversidadesFilters) => {
  return useQuery<UniversidadList, Error>({
    queryKey: universidadesKeys.list(filters),
    queryFn: () => universidadesService.getAll(filters),
  });
};

export const useCreateUniversidad = () => {
  const queryClient = useQueryClient();

  return useMutation<Universidad, Error, UniversidadCreate>({
    mutationFn: (payload) => universidadesService.create(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: universidadesKeys.all });
      toast.success('Universidad creada');
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo crear la universidad');
    },
  });
};

export const useUpdateUniversidad = () => {
  const queryClient = useQueryClient();

  return useMutation<Universidad, Error, { id: number; payload: UniversidadUpdate }>({
    mutationFn: ({ id, payload }) => universidadesService.update(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: universidadesKeys.all });
      toast.success('Universidad actualizada');
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo actualizar la universidad');
    },
  });
};

export const useDeleteUniversidad = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, number>({
    mutationFn: (id) => universidadesService.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: universidadesKeys.all });
      toast.success('Universidad dada de baja');
    },
    onError: (error) => {
      toast.error(error.message || 'No se pudo dar de baja la universidad');
    },
  });
};
