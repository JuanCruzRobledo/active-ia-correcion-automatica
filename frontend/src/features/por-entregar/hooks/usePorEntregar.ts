import { useQuery } from '@tanstack/react-query';
import { getPorEntregar } from '../services/por-entregar.service';

export const POR_ENTREGAR_QUERY_KEY = ['por-entregar'] as const;

/**
 * Lista local (instantánea) de correcciones pendientes de subir a Moodle.
 * No consulta Moodle: sale de nuestra propia base, por eso es rápida.
 */
export function usePorEntregar() {
  return useQuery({
    queryKey: POR_ENTREGAR_QUERY_KEY,
    queryFn: getPorEntregar,
    staleTime: 30 * 1000, // dato local; se invalida al subir
  });
}
