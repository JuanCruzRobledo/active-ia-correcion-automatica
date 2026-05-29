// features/entregas/services/moodle-grade.service.ts
/**
 * Service para subir corrección + devolución a Moodle (Fase 3).
 *
 * El preview/subir del backend son por correccion_id, pero desde la UI tenemos
 * el entrega_id; se resuelve el correccion_id vía GET /correcciones/entregas/{id}.
 */

import { apiClient } from '@/shared/services/api-client';
import type {
  Correccion,
  PreviewMoodle,
  PreviewMoodleResult,
  SubirMoodleResponse,
} from '../types';

export const moodleGradeService = {
  /** Resuelve la corrección de la entrega y trae el preview de lo que se enviaría. */
  getPreviewByEntrega: async (entregaId: number): Promise<PreviewMoodleResult> => {
    const { data: correccion } = await apiClient.get<Correccion>(
      `/correcciones/entregas/${entregaId}`
    );
    const { data: preview } = await apiClient.get<PreviewMoodle>(
      `/correcciones/${correccion.id}/moodle/preview`
    );
    return { correccionId: correccion.id, preview };
  },

  /** Publica la nota + feedback en Moodle. */
  subir: async (
    correccionId: number,
    comentario: string,
    forzar = false
  ): Promise<SubirMoodleResponse> => {
    const { data } = await apiClient.post<SubirMoodleResponse>(
      `/correcciones/${correccionId}/moodle`,
      { comentario, forzar }
    );
    return data;
  },
};
