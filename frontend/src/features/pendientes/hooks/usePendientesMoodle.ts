import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getPendientesMoodle } from '../services/pendientes.service';
import type { MateriasPendientesResponse } from '../types';

export const PENDIENTES_QUERY_KEY = ['pendientes-moodle'] as const;

export function usePendientesMoodle() {
  const queryClient = useQueryClient();

  const query = useQuery<MateriasPendientesResponse, Error>({
    queryKey: PENDIENTES_QUERY_KEY,
    queryFn: getPendientesMoodle,
    staleTime: 5 * 60 * 1000,
  });

  const refresh = () => {
    // Borra el cache y deja que el observer re-fetche automáticamente,
    // idéntico al comportamiento del primer render (como F5).
    queryClient.removeQueries({ queryKey: PENDIENTES_QUERY_KEY });
  };

  return {
    ...query,
    isRefreshing: query.isFetching && !query.isLoading,
    refresh,
  };
}
