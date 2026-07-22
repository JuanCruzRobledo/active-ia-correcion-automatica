import { describe, it, expect } from 'vitest';
import { distribuirPesosIguales } from './distribuirPesosIguales';

/**
 * peso-por-subcriterio (fase 7.5, design D4): al migrar una rúbrica v1 a v2, se
 * precarga un reparto de pesos iguales entre los subcriterios de un criterio,
 * usando el método del resto mayor (Hamilton) para garantizar suma exacta con
 * enteros:
 *   base = floor(peso / n)
 *   resto = peso - base * n
 *   los primeros `resto` subcriterios reciben base + 1; el resto, base
 */
describe('distribuirPesosIguales', () => {
  it('reparto exacto sin resto (25 entre 5)', () => {
    expect(distribuirPesosIguales(25, 5)).toEqual([5, 5, 5, 5, 5]);
  });

  it('reparto con resto (25 entre 3) — primeros `resto` reciben +1', () => {
    // base = floor(25/3) = 8, resto = 1 -> [9, 8, 8]
    expect(distribuirPesosIguales(25, 3)).toEqual([9, 8, 8]);
  });

  it('la suma siempre da exactamente el peso del criterio (triangulación con varios n)', () => {
    for (const [peso, n] of [[10, 3], [7, 4], [100, 7], [1, 1], [30, 6]] as const) {
      const pesos = distribuirPesosIguales(peso, n);
      expect(pesos.reduce((a, b) => a + b, 0)).toBe(peso);
      expect(pesos).toHaveLength(n);
    }
  });

  it('caso borde: peso_criterio < n — algunos quedan en 0, la suma sigue exacta', () => {
    // peso=2, n=5 -> base=0, resto=2 -> [1, 1, 0, 0, 0]
    const pesos = distribuirPesosIguales(2, 5);
    expect(pesos).toEqual([1, 1, 0, 0, 0]);
    expect(pesos.reduce((a, b) => a + b, 0)).toBe(2);
  });

  it('n = 1: todo el peso va al único subcriterio', () => {
    expect(distribuirPesosIguales(40, 1)).toEqual([40]);
  });

  it('n = 0: devuelve arreglo vacío sin lanzar', () => {
    expect(distribuirPesosIguales(10, 0)).toEqual([]);
  });
});
