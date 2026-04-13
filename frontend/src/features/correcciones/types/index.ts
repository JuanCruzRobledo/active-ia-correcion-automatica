// features/correcciones/types/index.ts
/**
 * Types for correcciones (corrections) feature.
 * Based on backend schemas from skills/correccion-ia/SKILL.md
 */

/**
 * Estado de evaluación de un criterio.
 */
export type EstadoCriterio = 'OK' | 'WARNING' | 'ERROR';

/**
 * Criterio evaluado en una corrección.
 */
export interface CriterioEvaluado {
  id: string;
  nombre: string;
  puntaje_obtenido: number;
  puntaje_maximo: number;
  estado: EstadoCriterio;
  feedback: string;
}

/**
 * Corrección completa de una entrega.
 */
export interface Correccion {
  id: number;
  entrega_id: number;
  nota: number;
  nota_antes_penalizaciones: number | null;
  condicion_desaprobacion_aplicada: string | null;
  condicion_desaprobacion_descripcion: string | null;
  penalizaciones_aplicadas: string[];
  penalizaciones_descripciones: { id: string; descripcion: string; descuento_porcentaje: number }[];
  criterios: CriterioEvaluado[];
  fortalezas: string[];
  recomendaciones: string[];
  comentario_general: string;
  editado_manualmente: boolean;
  fecha_correccion: string; // ISO 8601 datetime
}

/**
 * Datos para editar una corrección existente.
 * Todos los campos son opcionales.
 */
export interface CorreccionUpdate {
  nota?: number;
  nota_antes_penalizaciones?: number | null;
  condicion_desaprobacion_aplicada?: string | null;
  penalizaciones_aplicadas?: string[];
  criterios?: CriterioEvaluado[];
  fortalezas?: string[];
  recomendaciones?: string[];
  comentario_general?: string;
}

/**
 * Request para corrección en lote.
 */
export interface CorregirLoteRequest {
  entrega_ids: number[];
}
