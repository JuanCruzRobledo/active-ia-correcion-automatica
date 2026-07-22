// features/rubricas/utils/rubricaPortableJson.ts
/**
 * "Shape portable" de una rúbrica: el JSON reusable que se exporta e importa.
 *
 * Es el idioma común de la feature (handoff JSON portable):
 *   - dropdown de la lista (`RubricasPage`) → baja el JSON de una rúbrica guardada,
 *   - botón del modal (`RubricaEditor`) → baja el JSON de lo que se está editando,
 *   - importador (`handleLoadJSON`) → pega/sube un JSON para autocompletar el form.
 *
 * Deliberadamente NO incluye identidad de instancia (id, materia_id, tipo, numero,
 * anio, activa, moodle_assign_id, timestamps): eso ata el JSON a UNA rúbrica puntual
 * y rompe el caso de uso principal ("bajo este JSON y armo otra rúbrica en otra
 * materia/año"). El JSON portable es CONTENIDO reusable, no una instancia.
 */

import type {
  Criterio,
  Penalizacion,
  CondicionDesaprobacion,
  ModoConsolidacion,
} from '../types';

/** Los 4 modos de consolidación válidos (fuente de verdad compartida con el backend). */
export const MODOS_CONSOLIDACION_VALIDOS: readonly ModoConsolidacion[] = [
  'solo_codigo',
  'web_completo',
  'proyecto_completo',
  'personalizado',
];

/**
 * Entrada de `buildRubricaPortableJSON`. Todos los campos son opcionales: los
 * consumidores pasan valores de `watch()` (que pueden ser undefined mientras el
 * form se arma) o de un `RubricaDetail`; los defaults se resuelven acá.
 */
export interface RubricaPortableInput {
  titulo?: string;
  descripcion?: string;
  metadata?: Record<string, unknown>;
  criterios?: Criterio[];
  penalizaciones?: Penalizacion[];
  condiciones_desaprobacion?: CondicionDesaprobacion[];
  modo_consolidacion?: ModoConsolidacion;
  extensiones_personalizadas?: string[] | null;
}

/** Objeto exacto que se serializa al archivo `.json`. */
export interface RubricaPortableJSON {
  titulo: string;
  descripcion: string;
  metadata: Record<string, unknown>;
  criterios: Criterio[];
  penalizaciones: Penalizacion[];
  condiciones_desaprobacion: CondicionDesaprobacion[];
  modo_consolidacion: ModoConsolidacion;
  extensiones_personalizadas: string[] | null;
}

/**
 * Construye el shape portable normalizando defaults. Regla dura:
 * `extensiones_personalizadas` solo sobrevive si el modo es `personalizado`
 * (en cualquier otro modo se fuerza a `null`, coherente con el submit del editor).
 */
export function buildRubricaPortableJSON(
  data: RubricaPortableInput
): RubricaPortableJSON {
  const modo = data.modo_consolidacion ?? 'solo_codigo';
  return {
    titulo: data.titulo ?? '',
    descripcion: data.descripcion ?? '',
    metadata: data.metadata ?? {},
    criterios: data.criterios ?? [],
    penalizaciones: data.penalizaciones ?? [],
    condiciones_desaprobacion: data.condiciones_desaprobacion ?? [],
    modo_consolidacion: modo,
    extensiones_personalizadas:
      modo === 'personalizado' ? (data.extensiones_personalizadas ?? []) : null,
  };
}

/**
 * Type guard: `true` si `value` es uno de los 4 modos válidos. Se usa al importar
 * para autocompletar el selector SOLO cuando el JSON trae un modo real; un valor
 * inválido (typo, mayúsculas, otra fuente) se ignora sin romper la importación.
 */
export function esModoConsolidacionValido(
  value: unknown
): value is ModoConsolidacion {
  return (
    typeof value === 'string' &&
    MODOS_CONSOLIDACION_VALIDOS.includes(value as ModoConsolidacion)
  );
}

/**
 * Dispara la descarga del JSON portable como archivo `.json` en el cliente.
 * Mismo patrón Blob + link que `rubricasService.downloadPDF`, pero 100% cliente
 * (el objeto ya está en memoria; no se pega a ningún endpoint).
 */
export function descargarRubricaJSON(
  portable: RubricaPortableJSON,
  filename: string
): void {
  const contenido = JSON.stringify(portable, null, 2);
  const blob = new Blob([contenido], { type: 'application/json' });
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
