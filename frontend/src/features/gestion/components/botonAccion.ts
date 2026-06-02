/** Clase del botón de acción de Gestión: color base, color distinto cuando está
 *  "activo" (operación en curso), y estilo deshabilitado. */
export function botonAccionCls(activo: boolean): string {
  return [
    'flex cursor-pointer items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-50',
    activo ? 'bg-warning text-white' : 'bg-accent text-accent-foreground hover:opacity-90',
  ].join(' ');
}
