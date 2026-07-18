// features/rubricas/utils/distribuirPesosIguales.ts
/**
 * Reparto de pesos iguales entre subcriterios (migración v1 → v2).
 *
 * Método del resto mayor (Hamilton) — design.md D4 de peso-por-subcriterio:
 *   base = floor(peso / n)
 *   resto = peso - base * n           (0 <= resto < n)
 *   los primeros `resto` subcriterios reciben base + 1; el resto, base
 *
 * Garantiza que `sum(resultado) === peso` exacto con enteros, sin importar si
 * `peso / n` es entero o no. Si `peso < n` (más subcriterios que puntos), no
 * todos pueden recibir >= 1: el resultado deja algunos en 0 — es un caso borde
 * documentado, no un error; la validación Zod/backend de v2 exige `peso >= 1`
 * en cada subcriterio, así que ese reparto pre-cargado obliga al docente a
 * ajustar a mano antes de guardar.
 */
export function distribuirPesosIguales(peso: number, n: number): number[] {
  if (n <= 0) return [];

  const base = Math.floor(peso / n);
  const resto = peso - base * n;

  return Array.from({ length: n }, (_, i) => (i < resto ? base + 1 : base));
}
