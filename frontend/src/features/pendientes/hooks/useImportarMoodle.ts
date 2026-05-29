import { useMutation, useQueryClient } from '@tanstack/react-query';
import { importarMoodle } from '../services/pendientes.service';
import type { ImportarMoodleRequest, ImportarMoodleResponse } from '../types';
import { PENDIENTES_QUERY_KEY } from './usePendientesMoodle';

/**
 * Mutation para importar entregas pendientes desde Moodle.
 * Al completar, invalida los pendientes (cambian los conteos) y las entregas.
 */
export function useImportarMoodle() {
  const queryClient = useQueryClient();

  return useMutation<ImportarMoodleResponse, Error, ImportarMoodleRequest>({
    mutationFn: importarMoodle,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: PENDIENTES_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: ['entregas'] });
    },
  });
}
