// Formateo de fechas en horario de Argentina (America/Argentina/Buenos_Aires).
//
// El backend persiste los timestamps en UTC y los serializa SIN marca de zona
// (ej. "2026-06-03T03:00:00"). Si se los pasa tal cual a `new Date()`, el navegador
// los interpreta como hora LOCAL → aparecen +3hs. Acá los tratamos como UTC y los
// mostramos siempre en hora Argentina, sin importar la zona del navegador.

const TZ_ARGENTINA = 'America/Argentina/Buenos_Aires';

/** Parsea un ISO asumiendo UTC si no trae zona horaria (lo que envía el backend). */
function aFecha(iso: string): Date {
  const tieneZona = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso);
  // Solo agregamos 'Z' a datetimes (con 'T'); las fechas puras ya son UTC por spec.
  return new Date(tieneZona || !iso.includes('T') ? iso : `${iso}Z`);
}

/** Fecha + hora en horario Argentina. Ej: "3/6/26 00:00". '—' si es nulo. */
export function formatFechaHoraArg(iso: string | null | undefined): string {
  if (!iso) return '—';
  return aFecha(iso).toLocaleString('es-AR', {
    timeZone: TZ_ARGENTINA,
    dateStyle: 'short',
    timeStyle: 'short',
  });
}

/** Solo fecha en horario Argentina. Ej: "03/06/2026". '—' si es nulo. */
export function formatFechaArg(iso: string | null | undefined): string {
  if (!iso) return '—';
  return aFecha(iso).toLocaleDateString('es-AR', {
    timeZone: TZ_ARGENTINA,
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}
