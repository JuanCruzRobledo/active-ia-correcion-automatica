import { useMutation, useQuery } from '@tanstack/react-query';
import {
  consultarGestion,
  getCursos,
  getFiltros,
} from '../services/gestion.service';
import type { FiltrosGestion } from '../types';

/** Cursos elegibles (materias vinculadas a Moodle). */
export function useCursosGestion() {
  return useQuery({
    queryKey: ['gestion', 'cursos'],
    queryFn: getCursos,
    staleTime: 5 * 60 * 1000,
  });
}

/** Opciones de filtro (regionales/comisiones + catálogos) del curso elegido. */
export function useFiltrosGestion(materiaId: number | null) {
  return useQuery({
    queryKey: ['gestion', 'filtros', materiaId],
    queryFn: () => getFiltros(materiaId as number),
    enabled: materiaId != null,
    staleTime: 5 * 60 * 1000,
  });
}

/** Consulta (POST con filtros): se dispara con el botón "Consultar". */
export function useConsultaGestion() {
  return useMutation({
    mutationFn: ({
      materiaId,
      filtros,
    }: {
      materiaId: number;
      filtros: FiltrosGestion;
    }) => consultarGestion(materiaId, filtros),
  });
}
