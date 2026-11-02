/** Análisis de la versión entregada; ausente en entregas anteriores a la política. */
export interface AnalisisArchivos {
  version: number;
  archivos_incluidos: string[];
  archivos_ignorados: { ruta: string; motivo: string }[];
  rutas_penalizables: string[];
  limite_nota: number | null;
  directorios_permitidos: string[];
  moodle_timemodified?: number;
}
