import { describe, expect, it } from 'vitest';
import type { CriterioEvaluado } from '../types';
import { actualizarSubcriterio, normalizarCriterios, erroresSubcriterios, sumarPuntajes } from './edicionSubcriterios';

const criterio = (id = 'C1'): CriterioEvaluado => ({
  id, nombre: id, puntaje_obtenido: 9, puntaje_maximo: 20, estado: 'WARNING', feedback: 'Padre',
  subcriterios_evaluados: [
    { id: `${id}.1`, puntaje_obtenido: 0.1, puntaje_maximo: 10, estado: 'OK', feedback: 'Uno' },
    { id: `${id}.2`, puntaje_obtenido: 0.2, puntaje_maximo: 10, estado: 'ERROR', feedback: 'Dos' },
  ],
});

describe('edición inmutable del desglose', () => {
  it('normaliza texto numérico sin reparar el total histórico y copia el desglose', () => {
    const source = criterio();
    source.subcriterios_evaluados![0].puntaje_obtenido = '2.5' as unknown as number;
    source.subcriterios_evaluados![0].puntaje_maximo = '10' as unknown as number;
    const copy = normalizarCriterios([source]);
    expect(copy[0].puntaje_obtenido).toBe(9);
    expect(copy[0].subcriterios_evaluados![0].puntaje_obtenido).toBe(2.5);
    expect(copy[0].subcriterios_evaluados![0].puntaje_maximo).toBe(10);
    expect(copy[0].subcriterios_evaluados![0]).not.toBe(source.subcriterios_evaluados![0]);
  });
  it.each([undefined, null, []])('conserva ausencia de desglose %s', value => {
    expect(normalizarCriterios([{ ...criterio(), subcriterios_evaluados: value }])[0].subcriterios_evaluados).toEqual(value);
  });
  it('actualiza por IDs, suma decimales y conserva hermanos y metadatos', () => {
    const source = [criterio(), criterio('C2')];
    const result = actualizarSubcriterio(source, 'C1', 'C1.1', 'puntaje_obtenido', 0.2);
    expect(result[0].puntaje_obtenido).toBe(0.4);
    expect(result[0].subcriterios_evaluados![0]).toEqual({ ...source[0].subcriterios_evaluados![0], puntaje_obtenido: 0.2 });
    expect(result[0].subcriterios_evaluados![1]).toEqual(source[0].subcriterios_evaluados![1]);
    expect(result[1]).toBe(source[1]);
    expect(source[0].puntaje_obtenido).toBe(9);
    expect(source[0].subcriterios_evaluados![0].puntaje_obtenido).toBe(0.1);
  });
  it('cambiar comentario o reenviar mismo puntaje preserva total histórico', () => {
    const source = [criterio()];
    expect(actualizarSubcriterio(source, 'C1', 'C1.1', 'feedback', 'Nuevo')[0].puntaje_obtenido).toBe(9);
    expect(actualizarSubcriterio(source, 'C1', 'C1.1', 'puntaje_obtenido', 0.1)[0].puntaje_obtenido).toBe(9);
  });
  it('suma 0.1 + 0.2 sin ruido binario y soporta exponentes', () => {
    expect(sumarPuntajes([0.1, 0.2])).toBe(0.3);
    expect(sumarPuntajes([1e-7, 2e-7])).toBe(3e-7);
  });
  it.each([-1, 11, NaN, Infinity])('rechaza puntaje %s', value => {
    const data = [criterio()]; data[0].subcriterios_evaluados![0].puntaje_obtenido = value;
    expect(erroresSubcriterios(data)['C1/C1.1']).toMatch(/puntaje/i);
  });
  it.each([0, 10, 2.5])('acepta límite/decimal %s', value => {
    const data = [criterio()]; data[0].subcriterios_evaluados![0].puntaje_obtenido = value;
    expect(erroresSubcriterios(data)).toEqual({});
  });
  it.each(['', '   '])('rechaza comentario vacío %s', feedback => {
    const data = [criterio()]; data[0].subcriterios_evaluados![0].feedback = feedback;
    expect(erroresSubcriterios(data)['C1/C1.1']).toMatch(/comentario/i);
  });
  it('bloquea una suma mayor al máximo del criterio', () => {
    const data = [criterio()]; data[0].puntaje_obtenido = 21;
    expect(erroresSubcriterios(data).C1).toMatch(/suma.*máximo/i);
  });
  it('actualizar otro ID no altera el snapshot y entrada no finita no se suma', () => {
    const source = [criterio()];
    expect(actualizarSubcriterio(source, 'C1', 'desconocido', 'feedback', 'Texto')[0]).toBe(source[0]);
    expect(sumarPuntajes([1, NaN])).toBeNaN();
  });
  it('restaura total histórico cuando todos los puntajes vuelven al snapshot', () => {
    const original = [criterio()];
    const changed = actualizarSubcriterio(original, 'C1', 'C1.1', 'puntaje_obtenido', 2, original);
    expect(changed[0].puntaje_obtenido).toBe(2.2);
    expect(actualizarSubcriterio(changed, 'C1', 'C1.1', 'puntaje_obtenido', 0.1, original)[0].puntaje_obtenido).toBe(9);
  });
});
