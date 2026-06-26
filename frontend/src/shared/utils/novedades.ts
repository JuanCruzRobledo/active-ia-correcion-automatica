import type { Rol } from '@/shared/types';

/**
 * Mensaje del banner "hay novedades" según el rol (item #2, Capa B).
 *
 * Se mantiene mínimo a propósito: el TUTOR es quien corrige, así que se le habla de
 * entregas; los demás roles reciben un aviso genérico para no exponer más información
 * de la que necesitan.
 */
export function mensajeNovedades(rol: Rol | null | undefined): string {
  if (rol === 'TUTOR') return 'Hay entregas nuevas para corregir.';
  if (rol === 'ADMIN' || rol === 'COORDINADOR' || rol === 'GESTOR') {
    return 'Hay datos actualizados.';
  }
  return 'Hay novedades.';
}
