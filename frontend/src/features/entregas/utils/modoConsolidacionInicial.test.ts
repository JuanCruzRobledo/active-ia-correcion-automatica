import { describe, it, expect } from 'vitest';
import { getModoConsolidacionInicial } from './modoConsolidacionInicial';

/**
 * Regla de negocio: al abrir el modal de subida manual, el modo de
 * consolidación se pre-rellena con el que tiene la rúbrica (definido al
 * crearla). La rúbrica lo guarda en minúscula ('web_completo'); el form lo
 * usa en mayúscula ('WEB_COMPLETO'). Si es 'personalizado', se arrastran las
 * extensiones de la rúbrica. El usuario puede editarlo después.
 */
describe('getModoConsolidacionInicial', () => {
  it('mapea el modo de la rúbrica de minúscula a mayúscula del form', () => {
    const result = getModoConsolidacionInicial({
      modo_consolidacion: 'web_completo',
      extensiones_personalizadas: null,
    });

    expect(result).toEqual({ modo: 'WEB_COMPLETO', extensiones: [] });
  });

  it('en personalizado arrastra las extensiones de la rúbrica', () => {
    const result = getModoConsolidacionInicial({
      modo_consolidacion: 'personalizado',
      extensiones_personalizadas: ['.ipynb', '.sql'],
    });

    expect(result).toEqual({
      modo: 'PERSONALIZADO',
      extensiones: ['.ipynb', '.sql'],
    });
  });

  it('en solo_codigo no arrastra extensiones aunque la rúbrica las tenga', () => {
    const result = getModoConsolidacionInicial({
      modo_consolidacion: 'solo_codigo',
      extensiones_personalizadas: ['.py'],
    });

    expect(result).toEqual({ modo: 'SOLO_CODIGO', extensiones: [] });
  });

  it('sin rúbrica (undefined) cae al default WEB_COMPLETO', () => {
    expect(getModoConsolidacionInicial(undefined)).toEqual({
      modo: 'WEB_COMPLETO',
      extensiones: [],
    });
  });

  it('rúbrica sin modo seteado cae al default WEB_COMPLETO', () => {
    expect(
      getModoConsolidacionInicial({
        modo_consolidacion: null,
        extensiones_personalizadas: null,
      })
    ).toEqual({ modo: 'WEB_COMPLETO', extensiones: [] });
  });

  it('personalizado sin extensiones devuelve lista vacía (no null)', () => {
    const result = getModoConsolidacionInicial({
      modo_consolidacion: 'personalizado',
      extensiones_personalizadas: null,
    });

    expect(result).toEqual({ modo: 'PERSONALIZADO', extensiones: [] });
  });
});
