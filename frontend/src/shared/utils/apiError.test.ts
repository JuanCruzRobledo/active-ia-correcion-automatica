import { describe, it, expect } from 'vitest';
import { extractDetailMessage } from './apiError';

describe('extractDetailMessage (ERR-005: parseo unificado del detail)', () => {
  it('detail string: lo devuelve tal cual', () => {
    expect(extractDetailMessage('No tenés permisos.')).toBe('No tenés permisos.');
  });

  it('detail objeto { error_code, message }: devuelve message (caso IA)', () => {
    expect(
      extractDetailMessage({
        error_code: 'GEMINI_OVERLOADED',
        message: 'El modelo de Gemini está sobrecargado. Reintentá en unos minutos.',
      })
    ).toBe('El modelo de Gemini está sobrecargado. Reintentá en unos minutos.');
  });

  it('detail array de validación (Pydantic): une los msg', () => {
    expect(
      extractDetailMessage([{ msg: 'campo requerido' }, { msg: 'debe ser número' }])
    ).toBe('campo requerido; debe ser número');
  });

  it('detail objeto solo con error_code (sin message): devuelve undefined', () => {
    expect(extractDetailMessage({ error_code: 'SIN_CREDITOS' })).toBeUndefined();
  });

  it('undefined / null / string vacío: devuelve undefined (para que el caller use su fallback)', () => {
    expect(extractDetailMessage(undefined)).toBeUndefined();
    expect(extractDetailMessage(null)).toBeUndefined();
    expect(extractDetailMessage('')).toBeUndefined();
  });

  it('array vacío o sin msg: devuelve undefined', () => {
    expect(extractDetailMessage([])).toBeUndefined();
    expect(extractDetailMessage([{}, {}])).toBeUndefined();
  });
});
