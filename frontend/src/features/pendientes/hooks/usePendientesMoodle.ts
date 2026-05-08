import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getPendientesMoodle } from '../services/pendientes.service';
import type { MateriasPendientesResponse } from '../types';

export const PENDIENTES_QUERY_KEY = ['pendientes-moodle'] as const;

export function usePendientesMoodle() {
  const queryClient = useQueryClient();
  const [isRefreshing, setIsRefreshing] = useState(false);
  const refreshingRef = useRef(false);

  const query = useQuery<MateriasPendientesResponse, Error>({
    queryKey: PENDIENTES_QUERY_KEY,
    queryFn: getPendientesMoodle,
    staleTime: 5 * 60 * 1000,
    placeholderData: (prev) => prev,
  });

  // Cuando isFetching vuelve a false después de un refresh manual, apagamos el spinner
  useEffect(() => {
    if (refreshingRef.current && !query.isFetching) {
      refreshingRef.current = false;
      setIsRefreshing(false);
    }
  }, [query.isFetching]);

  const refresh = () => {
    if (refreshingRef.current) return;
    refreshingRef.current = true;
    setIsRefreshing(true);
    queryClient.removeQueries({ queryKey: PENDIENTES_QUERY_KEY });
  };

  return { ...query, isRefreshing, refresh };
}
