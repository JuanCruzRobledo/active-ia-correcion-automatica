import { useQuery } from '@tanstack/react-query';
import { getPendientesMoodle } from '../services/pendientes.service';
import type { MateriasPendientesResponse } from '../types';

export function usePendientesMoodle() {
  const query = useQuery<MateriasPendientesResponse, Error>({
    queryKey: ['pendientes-moodle'],
    queryFn: getPendientesMoodle,
    staleTime: 5 * 60 * 1000,
  });

  return { ...query, isRefreshing: query.isFetching && !query.isLoading };
}
