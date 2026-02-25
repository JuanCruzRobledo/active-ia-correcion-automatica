// features/rubricas/hooks/useRubricas.ts
/**
 * React Query hooks for Rubricas feature.
 *
 * Provides data fetching and mutation hooks with automatic caching and invalidation.
 * Ref: .claude/rules/frontend.md - React Query patterns
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { rubricasService } from '../services/rubricas-service';
import type {
  RubricaCreate,
  RubricaUpdate,
  RubricaDuplicar,
  RubricasFilters,
} from '../types';

/**
 * Query key factory for rubricas
 */
const rubricasKeys = {
  all: ['rubricas'] as const,
  lists: () => [...rubricasKeys.all, 'list'] as const,
  list: (filters?: RubricasFilters) => [...rubricasKeys.lists(), filters] as const,
  details: () => [...rubricasKeys.all, 'detail'] as const,
  detail: (id: number) => [...rubricasKeys.details(), id] as const,
};

/**
 * Hook to fetch paginated list of rubricas
 */
export const useRubricas = (filters?: RubricasFilters) => {
  return useQuery({
    queryKey: rubricasKeys.list(filters),
    queryFn: () => rubricasService.getAll(filters),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to fetch a single rubrica by ID with full details
 */
export const useRubrica = (id: number) => {
  return useQuery({
    queryKey: rubricasKeys.detail(id),
    queryFn: () => rubricasService.getById(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

/**
 * Hook to create a new rubrica
 */
export const useCreateRubrica = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RubricaCreate) => rubricasService.create(data),
    onSuccess: () => {
      // Invalidate all rubrica lists to refetch with new data
      queryClient.invalidateQueries({ queryKey: rubricasKeys.lists() });
    },
  });
};

/**
 * Hook to update an existing rubrica
 */
export const useUpdateRubrica = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RubricaUpdate }) =>
      rubricasService.update(id, data),
    onSuccess: (updatedRubrica) => {
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: rubricasKeys.lists() });
      // Update the specific rubrica in cache
      queryClient.setQueryData(
        rubricasKeys.detail(updatedRubrica.id),
        updatedRubrica
      );
    },
  });
};

/**
 * Hook to soft delete a rubrica
 */
export const useDeleteRubrica = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => rubricasService.delete(id),
    onSuccess: () => {
      // Invalidate all rubrica queries to refetch
      queryClient.invalidateQueries({ queryKey: rubricasKeys.all });
    },
  });
};

/**
 * Hook to restore a soft-deleted rubrica
 */
export const useRestoreRubrica = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => rubricasService.restore(id),
    onSuccess: (restoredRubrica) => {
      // Invalidate lists
      queryClient.invalidateQueries({ queryKey: rubricasKeys.lists() });
      // Update the specific rubrica in cache
      queryClient.setQueryData(
        rubricasKeys.detail(restoredRubrica.id),
        restoredRubrica
      );
    },
  });
};

/**
 * Hook to duplicate a rubrica to a new year
 */
export const useDuplicarRubrica = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: RubricaDuplicar }) =>
      rubricasService.duplicar(id, data),
    onSuccess: () => {
      // Invalidate all rubrica lists to show the new duplicate
      queryClient.invalidateQueries({ queryKey: rubricasKeys.lists() });
    },
  });
};

/**
 * Hook to generate rubrica from PDF using AI
 */
export const useGenerarRubricaDesdePDF = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      tipo,
      file,
    }: {
      materiaId?: number; // Optional params kept for backward compatibility
      tipo: string;
      anio?: number; // Optional params kept for backward compatibility
      file: File;
    }) => rubricasService.generarDesdePDF(tipo, file),
    onSuccess: () => {
      // Note: The backend returns suggested criteria, not a saved rubrica
      // The component should handle creating the actual rubrica after review
      queryClient.invalidateQueries({ queryKey: rubricasKeys.lists() });
    },
  });
};

/**
 * Hook to download rubrica as PDF
 */
export const useDownloadRubricaPDF = () => {
  return useMutation({
    mutationFn: ({ id, filename }: { id: number; filename?: string }) =>
      rubricasService.downloadPDF(id, filename),
  });
};

/**
 * Hook to download rubrica as SUMMARY PDF
 */
export const useDownloadRubricaPDFResumido = () => {
  return useMutation({
    mutationFn: ({ id, filename }: { id: number; filename?: string }) =>
      rubricasService.downloadPDFResumido(id, filename),
  });
};

/**
 * Hook to preview rubrica as PDF from form data
 */
export const usePreviewRubricaPDF = () => {
  return useMutation({
    mutationFn: (data: {
      materia_nombre: string;
      tipo: string;
      numero: number;
      anio: number;
      titulo: string;
      descripcion: string;
      puntaje_maximo: number;
      criterios: any[];
      penalizaciones: any[];
      condiciones_desaprobacion: any[];
    }) => rubricasService.previewPDF(data),
  });
};

/**
 * Hook to preview rubrica as SUMMARY PDF from form data
 */
export const usePreviewRubricaPDFResumido = () => {
  return useMutation({
    mutationFn: (data: {
      materia_nombre: string;
      tipo: string;
      numero: number;
      anio: number;
      titulo: string;
      descripcion: string;
      puntaje_maximo: number;
      criterios: any[];
      penalizaciones: any[];
      condiciones_desaprobacion: any[];
    }) => rubricasService.previewPDFResumido(data),
  });
};
