import { describe, it, expect } from 'vitest';
import { resumenErrores } from './erroresResumen';

/**
 * item #7: tras una corrección masiva, mostrar un resumen legible de los errores por
 * código (no códigos crudos). Función pura.
 */
describe('resumenErrores', () => {
  it('traduce los códigos a etiquetas legibles', () => {
    const r = resumenErrores({ GEMINI_RATE_LIMIT: 5, GEMINI_OVERLOADED: 2 });
    expect(r).toContain('5');
    expect(r.toLowerCase()).toContain('rate limit');
    expect(r).toContain('2');
    expect(r.toLowerCase()).toContain('sobrecarg');
  });

  it('separa varias categorías con un punto medio', () => {
    const r = resumenErrores({ GEMINI_RATE_LIMIT: 1, N8N_TIMEOUT: 1 });
    expect(r).toContain('·');
  });

  it('un código desconocido cae en "otros"', () => {
    expect(resumenErrores({ ALGO_RARO: 3 }).toLowerCase()).toContain('otros');
  });

  it('mapa vacío devuelve string vacío', () => {
    expect(resumenErrores({})).toBe('');
    expect(resumenErrores(undefined)).toBe('');
  });
});
