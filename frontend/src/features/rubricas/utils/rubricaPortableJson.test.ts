import { describe, it, expect } from 'vitest';
import {
  buildRubricaPortableJSON,
  esModoConsolidacionValido,
  MODOS_CONSOLIDACION_VALIDOS,
} from './rubricaPortableJson';
import type { Criterio } from '../types';

/**
 * Shape portable de rúbrica (JSON exportar/importar). Es el idioma común entre:
 *   - el dropdown de la lista (descarga desde una rúbrica guardada),
 *   - el botón del modal (descarga de lo que se está editando),
 *   - el importador (pegar/subir JSON para autocompletar el form).
 *
 * Reglas duras:
 *   1. SIEMPRE incluye `modo_consolidacion` (default `solo_codigo`).
 *   2. `extensiones_personalizadas` solo sobrevive si `modo_consolidacion === 'personalizado'`;
 *      en cualquier otro modo se fuerza a `null` (es identidad del modo personalizado).
 *   3. NO incluye identidad de instancia (id, materia_id, tipo, numero, anio, activa,
 *      moodle_assign_id, timestamps): el JSON es contenido reusable, no una instancia.
 */
const criterioEjemplo: Criterio = {
  id: 'C1',
  nombre: 'Criterio 1',
  descripcion: 'desc',
  peso: 100,
  subcriterios: [{ id: 'C1.1', descripcion: 'sub', evidencias: [] }],
};

describe('buildRubricaPortableJSON', () => {
  it('incluye modo_consolidacion y expone EXACTAMENTE las 8 claves portables (sin identidad de instancia)', () => {
    const portable = buildRubricaPortableJSON({
      titulo: 'T',
      descripcion: 'D',
      metadata: { lenguaje: 'python' },
      criterios: [criterioEjemplo],
      penalizaciones: [],
      condiciones_desaprobacion: [],
      modo_consolidacion: 'web_completo',
      extensiones_personalizadas: null,
    });

    expect(Object.keys(portable).sort()).toEqual(
      [
        'condiciones_desaprobacion',
        'criterios',
        'descripcion',
        'extensiones_personalizadas',
        'metadata',
        'modo_consolidacion',
        'penalizaciones',
        'titulo',
      ].sort()
    );
    expect(portable.modo_consolidacion).toBe('web_completo');
    // Identidad de instancia NUNCA viaja
    expect(portable).not.toHaveProperty('id');
    expect(portable).not.toHaveProperty('materia_id');
    expect(portable).not.toHaveProperty('tipo');
    expect(portable).not.toHaveProperty('moodle_assign_id');
  });

  it('modo personalizado: preserva las extensiones tal cual', () => {
    const portable = buildRubricaPortableJSON({
      titulo: 'T',
      descripcion: 'D',
      metadata: {},
      criterios: [criterioEjemplo],
      penalizaciones: [],
      condiciones_desaprobacion: [],
      modo_consolidacion: 'personalizado',
      extensiones_personalizadas: ['.ipynb', '.sql'],
    });
    expect(portable.modo_consolidacion).toBe('personalizado');
    expect(portable.extensiones_personalizadas).toEqual(['.ipynb', '.sql']);
  });

  it('modo NO personalizado: fuerza extensiones a null aunque vengan cargadas', () => {
    const portable = buildRubricaPortableJSON({
      titulo: 'T',
      descripcion: 'D',
      metadata: {},
      criterios: [criterioEjemplo],
      penalizaciones: [],
      condiciones_desaprobacion: [],
      modo_consolidacion: 'solo_codigo',
      // Basura que quedó en el form; no debe filtrarse al JSON.
      extensiones_personalizadas: ['.ipynb'],
    });
    expect(portable.extensiones_personalizadas).toBeNull();
  });

  it('personalizado sin extensiones: cae en [] (no null), listo para editar', () => {
    const portable = buildRubricaPortableJSON({
      titulo: 'T',
      descripcion: 'D',
      metadata: {},
      criterios: [criterioEjemplo],
      penalizaciones: [],
      condiciones_desaprobacion: [],
      modo_consolidacion: 'personalizado',
      extensiones_personalizadas: null,
    });
    expect(portable.extensiones_personalizadas).toEqual([]);
  });

  it('tolerancia a campos faltantes: aplica defaults sin lanzar', () => {
    // Simula un watch() con campos undefined mientras el form se está armando.
    const portable = buildRubricaPortableJSON({
      titulo: 'T',
      descripcion: 'D',
      criterios: [criterioEjemplo],
    });
    expect(portable.metadata).toEqual({});
    expect(portable.penalizaciones).toEqual([]);
    expect(portable.condiciones_desaprobacion).toEqual([]);
    expect(portable.modo_consolidacion).toBe('solo_codigo');
    expect(portable.extensiones_personalizadas).toBeNull();
  });
});

describe('esModoConsolidacionValido', () => {
  it('acepta los 4 modos válidos', () => {
    for (const modo of MODOS_CONSOLIDACION_VALIDOS) {
      expect(esModoConsolidacionValido(modo)).toBe(true);
    }
  });

  it('rechaza valores fuera del conjunto (JSON armado a mano con typo)', () => {
    expect(esModoConsolidacionValido('solo_código')).toBe(false);
    expect(esModoConsolidacionValido('SOLO_CODIGO')).toBe(false);
    expect(esModoConsolidacionValido('')).toBe(false);
    expect(esModoConsolidacionValido(undefined)).toBe(false);
    expect(esModoConsolidacionValido(null)).toBe(false);
    expect(esModoConsolidacionValido(42)).toBe(false);
  });
});
