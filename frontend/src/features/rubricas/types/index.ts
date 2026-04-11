// features/rubricas/types/index.ts
/**
 * TypeScript types for Rubricas feature.
 *
 * Mirrors backend schemas from app/schemas/rubrica.py
 * Ref: docs/specs/Rubrica.md
 */

export type TipoRubrica =
  | 'TP'
  | 'PARCIAL_1'
  | 'PARCIAL_2'
  | 'RECUPERATORIO_1'
  | 'RECUPERATORIO_2'
  | 'FINAL'
  | 'GLOBAL';

export type FuenteRubrica = 'manual' | 'pdf';

// ============================================================================
// Schema Types (Hierarchical)
// ============================================================================

/**
 * Subcriterio dentro de un criterio.
 *
 * Representa un aspecto específico a evaluar con evidencias verificables.
 */
export interface Subcriterio {
  id: string; // Format: "C1.1", "C2.3"
  descripcion: string;
  evidencias: string[]; // Checklist de evidencias para la IA
}

/**
 * Criterio de evaluación.
 *
 * Define un aspecto a evaluar con peso porcentual y subcriterios.
 */
export interface Criterio {
  id: string; // Format: "C1", "C2"
  nombre: string;
  descripcion: string;
  peso: number; // Peso en % (suma total = 100)
  instrucciones_puntuacion?: string | null;
  subcriterios: Subcriterio[];
}

/**
 * Penalización que se puede aplicar a una evaluación.
 */
export interface Penalizacion {
  id: string; // Format: "P1", "P2"
  descripcion: string;
  descuento_porcentaje: number; // 0-100
}

/**
 * Condición automática de desaprobación.
 */
export interface CondicionDesaprobacion {
  id: string; // Format: "CD1", "CD2"
  condicion: string;
  nota_maxima: number; // 0-100, techo de nota si se cumple la condición
}

/**
 * Estructura completa de una rúbrica.
 *
 * Incluye información general, metadata flexible, criterios jerárquicos,
 * penalizaciones y condiciones de desaprobación.
 */
export interface CriteriosStructure {
  titulo: string;
  descripcion: string;
  puntaje_maximo: number; // Siempre 100
  metadata: Record<string, any>; // Flexible: materia, carrera, lenguaje, framework, etc.
  criterios: Criterio[];
  penalizaciones: Penalizacion[];
  condiciones_desaprobacion: CondicionDesaprobacion[];
}

// ============================================================================
// Rubrica Entity Types
// ============================================================================

export interface MateriaInfo {
  id: number;
  codigo: string;
  nombre: string;
}

export interface Rubrica {
  id: number;
  materia_id: number;
  tipo: TipoRubrica;
  numero: number;
  anio: number;
  titulo: string;
  descripcion: string;
  puntaje_maximo: number;
  metadata_json: Record<string, any>;
  criterios_json: Criterio[];
  penalizaciones_json: Penalizacion[];
  condiciones_desaprobacion_json: CondicionDesaprobacion[];
  fuente: FuenteRubrica;
  archivo_original: string | null;
  activa: boolean;
  created_at: string;
  updated_at: string;
}

export interface RubricaDetail extends Rubrica {
  materia: MateriaInfo;
  num_entregas: number;
}

export interface RubricaListItem {
  id: number;
  materia_id: number;
  materia_nombre: string;
  materia_codigo: string;
  tipo: TipoRubrica;
  titulo: string;
  numero: number;
  anio: number;
  puntaje_maximo: number;
  num_criterios: number;
  num_entregas: number;
  activa: boolean;
  created_at: string;
}

export interface RubricaList {
  items: RubricaListItem[];
  total: number;
  page: number;
  per_page: number;
}

// ============================================================================
// Request/Form Types
// ============================================================================

export interface RubricaCreate {
  materia_id: number;
  tipo: TipoRubrica;
  numero: number;
  anio: number;
  titulo: string;
  descripcion: string;
  puntaje_maximo?: number; // Default 100
  metadata_json?: Record<string, any>;
  criterios_json: Criterio[];
  penalizaciones_json?: Penalizacion[];
  condiciones_desaprobacion_json?: CondicionDesaprobacion[];
  fuente?: FuenteRubrica;
  archivo_original?: string;
}

export interface RubricaUpdate {
  titulo?: string;
  descripcion?: string;
  metadata_json?: Record<string, any>;
  criterios_json?: Criterio[];
  penalizaciones_json?: Penalizacion[];
  condiciones_desaprobacion_json?: CondicionDesaprobacion[];
}

export interface RubricaDuplicar {
  nuevo_anio: number;
  nuevo_titulo?: string;
}

export interface RubricasFilters {
  materia_id?: number;
  tipo?: TipoRubrica;
  anio?: number;
  include_inactive?: boolean;
  page?: number;
  per_page?: number;
}
