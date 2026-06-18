// features/entregas/utils/modoConsolidacionInicial.ts
/**
 * Pre-relleno del modo de consolidación en el modal de subida manual.
 *
 * El modo lo define la RÚBRICA al crearse. La rúbrica lo guarda en minúscula
 * ('web_completo') y el form de entregas lo usa en mayúscula ('WEB_COMPLETO').
 * Esta función traduce el valor de la rúbrica al del form y arrastra las
 * extensiones personalizadas SOLO cuando el modo es 'personalizado'.
 *
 * Si la rúbrica no existe o no tiene modo, cae al default histórico del modal.
 */
import type { ModoConsolidacion } from '../types';

/** Datos mínimos de la rúbrica que mira esta función. */
interface RubricaModoSource {
  modo_consolidacion?: string | null;
  extensiones_personalizadas?: string[] | null;
}

export interface ModoConsolidacionInicial {
  modo: ModoConsolidacion;
  extensiones: string[];
}

const DEFAULT: ModoConsolidacionInicial = {
  modo: 'WEB_COMPLETO',
  extensiones: [],
};

export function getModoConsolidacionInicial(
  rubrica: RubricaModoSource | null | undefined
): ModoConsolidacionInicial {
  if (!rubrica?.modo_consolidacion) {
    return { ...DEFAULT, extensiones: [] };
  }

  const modo = rubrica.modo_consolidacion.toUpperCase() as ModoConsolidacion;
  const extensiones =
    modo === 'PERSONALIZADO' ? rubrica.extensiones_personalizadas ?? [] : [];

  return { modo, extensiones };
}
