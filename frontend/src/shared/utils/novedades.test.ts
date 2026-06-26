import { describe, it, expect } from 'vitest';
import { mensajeNovedades } from './novedades';

/**
 * item #2 (Capa B): cuando el backend cambió, mostramos un aviso. El mensaje depende
 * del rol para no dar más info de la necesaria: el TUTOR corrige, así que se le habla de
 * entregas; el resto recibe un aviso genérico.
 */
describe('mensajeNovedades', () => {
  it('al TUTOR le habla de entregas para corregir', () => {
    expect(mensajeNovedades('TUTOR')).toBe('Hay entregas nuevas para corregir.');
  });

  it('a COORDINADOR / GESTOR / ADMIN les da un aviso genérico', () => {
    expect(mensajeNovedades('COORDINADOR')).toBe('Hay datos actualizados.');
    expect(mensajeNovedades('GESTOR')).toBe('Hay datos actualizados.');
    expect(mensajeNovedades('ADMIN')).toBe('Hay datos actualizados.');
  });

  it('sin rol conocido, mensaje neutro', () => {
    expect(mensajeNovedades(null)).toBe('Hay novedades.');
    expect(mensajeNovedades(undefined)).toBe('Hay novedades.');
  });
});
