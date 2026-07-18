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
 * Subcriterio evaluado dentro de un criterio (rúbricas schema_version >= 2).
 * Ausente/`undefined` en correcciones viejas o de rúbricas schema_version = 1.
 */
export interface SubcriterioEvaluado {
  id: string;
  puntaje_obtenido: number;
  puntaje_maximo: number;
  estado: EstadoCriterio;
  feedback: string;
}

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
  /**
   * Desglose por subcriterio (rúbricas schema_version >= 2). Opcional: las
   * correcciones viejas o de rúbricas v1 no lo traen — el frontend debe
   * tolerar su ausencia y mostrar la corrección igual que hoy.
   */
  subcriterios_evaluados?: SubcriterioEvaluado[] | null;
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
