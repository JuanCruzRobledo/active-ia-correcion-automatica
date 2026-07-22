import { describe, it, expect } from 'vitest';
import {
  criterioSchema,
  subcriterioSchema,
  criteriosStructureSchema,
} from './rubrica-schema';

/**
 * peso-por-subcriterio (fase 6.2): el subcriterio gana un `peso` (puntos absolutos)
 * que debe sumar exactamente el `peso` del criterio contenedor — mismo patrón que
 * "los criterios suman 100" (criteriosStructureSchema), un nivel abajo.
 *
 * Compatibilidad v1: los subcriterios sin `peso` (formato viejo) siguen validando
 * igual que antes — la validación de suma solo se activa cuando algún subcriterio
 * de ese criterio trae `peso` (equivalente en el front a "se está editando como v2",
 * sin necesitar enhebrar `schema_version` como contexto de Zod).
 */
describe('subcriterioSchema', () => {
  const base = { id: 'C1.1', descripcion: 'desc', evidencias: ['e1'] };

  it('v1: acepta subcriterio sin peso', () => {
    const result = subcriterioSchema.safeParse(base);
    expect(result.success).toBe(true);
  });

  it('v2: acepta peso válido (1-100)', () => {
    const result = subcriterioSchema.safeParse({ ...base, peso: 10 });
    expect(result.success).toBe(true);
  });

  it('v2: rechaza peso 0', () => {
    const result = subcriterioSchema.safeParse({ ...base, peso: 0 });
    expect(result.success).toBe(false);
  });

  it('v2: rechaza peso > 100', () => {
    const result = subcriterioSchema.safeParse({ ...base, peso: 101 });
    expect(result.success).toBe(false);
  });
});

describe('criterioSchema — suma de pesos de subcriterios', () => {
  const criterioBase = {
    id: 'C1',
    nombre: 'Funcionalidad',
    descripcion: 'Evalua funcionalidad',
    peso: 25,
  };

  it('v1: subcriterios sin peso siguen validando igual que antes (sin exigir suma)', () => {
    const result = criterioSchema.safeParse({
      ...criterioBase,
      subcriterios: [
        { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'] },
        { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'] },
      ],
    });
    expect(result.success).toBe(true);
  });

  it('v2: subcriterios cuya suma coincide con el peso del criterio pasan', () => {
    const result = criterioSchema.safeParse({
      ...criterioBase,
      subcriterios: [
        { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'], peso: 9 },
        { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'], peso: 8 },
        { id: 'C1.3', descripcion: 'd3', evidencias: ['e3'], peso: 8 },
      ],
    });
    expect(result.success).toBe(true);
  });

  it('v2: subcriterios cuya suma NO coincide con el peso del criterio fallan', () => {
    const result = criterioSchema.safeParse({
      ...criterioBase,
      subcriterios: [
        { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'], peso: 10 },
        { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'], peso: 10 },
      ],
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(
        result.error.issues.some((i) => i.message.includes('25'))
      ).toBe(true);
    }
  });

  it('v2: un subcriterio sin peso mientras otros sí lo tienen falla (mezcla inválida)', () => {
    const result = criterioSchema.safeParse({
      ...criterioBase,
      subcriterios: [
        { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'], peso: 15 },
        { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'] },
      ],
    });
    expect(result.success).toBe(false);
  });
});

describe('criteriosStructureSchema — propagación de la validación de subcriterios', () => {
  // criteriosStructureSchema reusa criterioSchema tal cual (array(criterioSchema)),
  // así que la .superRefine de suma de subcriterios debe propagar sin duplicar lógica.
  const estructuraBase = {
    titulo: 'Rúbrica X',
    descripcion: 'desc',
    puntaje_maximo: 100,
    metadata: {},
    criterios: [
      {
        id: 'C1',
        nombre: 'Criterio 1',
        descripcion: 'd',
        peso: 100,
        subcriterios: [
          { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'], peso: 60 },
          { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'], peso: 30 },
        ],
      },
    ],
    penalizaciones: [],
    condiciones_desaprobacion: [],
  };

  it('rechaza cuando la suma de subcriterios no matchea el peso del criterio', () => {
    const result = criteriosStructureSchema.safeParse(estructuraBase);
    expect(result.success).toBe(false); // 60 + 30 = 90 !== 100
  });

  it('acepta cuando la suma de subcriterios matchea el peso del criterio', () => {
    const result = criteriosStructureSchema.safeParse({
      ...estructuraBase,
      criterios: [
        {
          ...estructuraBase.criterios[0],
          subcriterios: [
            { id: 'C1.1', descripcion: 'd1', evidencias: ['e1'], peso: 70 },
            { id: 'C1.2', descripcion: 'd2', evidencias: ['e2'], peso: 30 },
          ],
        },
      ],
    });
    expect(result.success).toBe(true);
  });
});
