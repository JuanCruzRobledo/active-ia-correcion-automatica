// features/rubricas/types/index.ts
/**
 * TypeScript types for Rubricas feature.
 *
 * Mirrors backend schemas from app/schemas/rubrica.py
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 6
 * Ref: docs/specs/06-MODELO-DATOS.md seccion 3.6
 */

export type TipoRubrica =
  | 'TP'
  | 'PARCIAL_1'
  | 'PARCIAL_2'
  | 'RECUPERATORIO_1'
  | 'RECUPERATORIO_2'
  | 'FINAL'
  | 'GLOBAL';

export type FuenteRubrica = 'MANUAL' | 'IA';

export interface NivelDesempeno {
  puntaje: number;
  descripcion: string;
}

export interface Criterio {
  id: string;
  nombre: string;
  descripcion: string;
  puntaje_maximo: number;
  niveles?: NivelDesempeno[];
}

export interface CriteriosStructure {
  puntaje_maximo: number;
  criterios: Criterio[];
}

export interface MateriaInfo {
  id: number;
  codigo: string;
  nombre: string;
}

export interface Rubrica {
  id: number;
  materia_id: number;
  tipo: TipoRubrica;
  nombre: string;
  numero: number;
  anio: number;
  criterios_json: CriteriosStructure;
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
  nombre: string;
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

export interface RubricaCreate {
  materia_id: number;
  tipo: TipoRubrica;
  nombre: string;
  numero: number;
  anio: number;
  criterios_json: CriteriosStructure;
  fuente?: FuenteRubrica;
  archivo_original?: string;
}

export interface RubricaUpdate {
  nombre?: string;
  criterios_json?: CriteriosStructure;
}

export interface RubricaDuplicar {
  nuevo_anio: number;
  nuevo_nombre?: string;
}

export interface RubricasFilters {
  materia_id?: number;
  tipo?: TipoRubrica;
  anio?: number;
  include_inactive?: boolean;
  page?: number;
  per_page?: number;
}
