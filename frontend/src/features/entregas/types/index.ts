// features/entregas/types/index.ts
/**
 * TypeScript types for Entregas feature.
 *
 * Mirrors backend schemas from app/schemas/entrega.py
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md seccion 7
 * Ref: docs/specs/06-MODELO-DATOS.md seccion 3.7
 */

export type EstadoEntrega = 'SUBIDA' | 'PENDIENTE' | 'CORREGIDA' | 'ERROR';

export type ModoConsolidacion =
  | 'SOLO_CODIGO' // .py, .java, .js, .ts, .c, .cpp, .go
  | 'WEB_COMPLETO' // + .html, .css, .json
  | 'PROYECTO_COMPLETO' // + .md, .txt, .yml, .xml
  | 'PERSONALIZADO'; // Usuario define extensiones

export interface ComisionInfo {
  id: number;
  nombre: string;
  anio: number;
  materia_codigo: string;
  materia_nombre: string;
}

export interface RubricaInfo {
  id: number;
  tipo: string;
  nombre: string;
  numero: number;
  anio: number;
}

export interface CorreccionInfo {
  id: number;
  nota: number;
  editado_manualmente: boolean;
  fecha_correccion: string;
}

export interface CriterioEvaluado {
  id: string;
  nombre: string;
  puntaje_obtenido: number;
  puntaje_maximo: number;
  estado: 'OK' | 'WARNING' | 'ERROR';
  feedback: string;
}

export interface Correccion {
  id: number;
  entrega_id: number;
  nota: number;
  criterios: CriterioEvaluado[];
  fortalezas: string[];
  recomendaciones: string[];
  comentario_general: string;
  fecha_correccion: string;
  editado_manualmente: boolean;
}

export interface CorregirLoteResponse {
  total: number;
  exitosas: number;
  fallidas: number;
  correcciones: Correccion[];
  errores: {
    entrega_id: number;
    error: string;
  }[];
}

export interface Entrega {
  id: number;
  comision_id: number;
  rubrica_id: number;
  alumno_nombre: string;
  archivo_nombre: string;
  archivo_ruta: string;
  archivo_tamanio: number;
  archivo_tipo: 'zip' | 'txt' | 'pdf' | 'individual';
  contenido_preview: string | null;
  estado: EstadoEntrega;
  hash_sha256: string | null;
  subido_por_id: number;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface EntregaDetail extends Entrega {
  comision: ComisionInfo;
  rubrica: RubricaInfo;
  correccion: CorreccionInfo | null;
  subido_por_nombre: string;
}

export interface EntregaListItem {
  id: number;
  comision_id: number;
  rubrica_id: number;
  alumno_nombre: string;
  archivo_nombre: string;
  archivo_tamanio: number;
  estado: EstadoEntrega;
  nota: number | null;
  tiene_correccion: boolean;
  created_at: string;
}

export interface EntregaList {
  items: EntregaListItem[];
  total: number;
  page: number;
  per_page: number;
}

export interface EntregaCreate {
  comision_id: number;
  rubrica_id: number;
  alumno_nombre: string;
  archivo: File;
  modo_consolidacion?: ModoConsolidacion;
  extensiones_personalizadas?: string[]; // Ej: ['.sql', '.sh']
  sobrescribir?: boolean;
}

export interface CargaMasivaCreate {
  comision_id: number;
  rubrica_id: number;
  archivo_zip: File;
  modo_consolidacion: ModoConsolidacion;
  extensiones_personalizadas?: string[];
  sobrescribir: boolean;
}

export interface EntregaResponse {
  id: number;
  alumno_nombre: string;
  archivo_nombre: string;
  estado: EstadoEntrega;
  mensaje: string;
}

export interface CargaMasivaResponse {
  exitosas: EntregaResponse[];
  errores: {
    alumno_nombre: string;
    error: string;
  }[];
  total_procesadas: number;
  total_exitosas: number;
  total_errores: number;
}

export interface EntregaContenido {
  entrega_id: number;
  alumno_nombre: string;
  /** True for PDF submissions; false for code (zip/txt/individual) */
  es_pdf: boolean;
  /** Consolidated code text — null for PDF submissions */
  contenido_consolidado: string | null;
  /** PDF content encoded in Base64 — null for code submissions */
  pdf_contenido_b64: string | null;
  archivos_incluidos: string[];
  total_lineas: number;
  total_caracteres: number;
}

export interface EntregasFilters {
  comision_id: number;
  rubrica_id: number;
  estado?: EstadoEntrega;
  search?: string; // Buscar por nombre de alumno
  include_inactive?: boolean;
  page?: number;
  per_page?: number;
}
