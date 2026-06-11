/** Clase del botón de acción de Gestión: color base, color distinto cuando está
 *  "activo" (operación en curso), y estilo deshabilitado.
 *  En mobile el botón es táctil (min-h 44px) y full-width; en sm: vuelve al
 *  ancho automático original. */
export function botonAccionCls(activo: boolean): string {
  return [
    'flex min-h-11 w-full cursor-pointer items-center justify-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
    'sm:w-auto sm:justify-start',
    'disabled:cursor-not-allowed disabled:opacity-50',
    activo ? 'bg-warning text-white' : 'bg-accent text-accent-foreground hover:opacity-90',
  ].join(' ');
}
