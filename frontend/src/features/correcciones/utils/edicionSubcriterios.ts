import type { CriterioEvaluado } from '../types';

/** Copies the editable snapshot; Decimal values from the API can arrive as text. */
export function normalizarCriterios(criterios: CriterioEvaluado[] = []): CriterioEvaluado[] {
  return criterios.map(c => ({
    ...c, puntaje_obtenido: Number(c.puntaje_obtenido), puntaje_maximo: Number(c.puntaje_maximo),
    ...(c.subcriterios_evaluados ? { subcriterios_evaluados: c.subcriterios_evaluados.map(s => ({
      ...s, puntaje_obtenido: Number(s.puntaje_obtenido), puntaje_maximo: Number(s.puntaje_maximo),
    })) } : {}),
  }));
}

/** Adds decimal representations without accumulating binary rounding errors. */
export function sumarPuntajes(values: number[]): number {
  if (values.some(v => !Number.isFinite(v))) return NaN;
  const parts = values.map(value => {
    const [coefficient, exponent = '0'] = value.toString().split('e');
    const decimals = coefficient.split('.')[1]?.length ?? 0;
    return { integer: BigInt(coefficient.replace('.', '')), scale: decimals - Number(exponent) };
  });
  const scale = Math.max(0, ...parts.map(p => p.scale));
  const integer = parts.reduce((sum, p) => sum + p.integer * 10n ** BigInt(scale - p.scale), 0n);
  return Number(`${integer}e-${scale}`);
}

export function actualizarSubcriterio(
  criterios: CriterioEvaluado[], criterioId: string, subId: string,
  field: 'puntaje_obtenido' | 'feedback', value: number | string,
  original?: CriterioEvaluado[],
): CriterioEvaluado[] {
  return criterios.map(c => {
    if (c.id !== criterioId) return c;
    const previous = c.subcriterios_evaluados?.find(s => s.id === subId);
    if (!previous) return c;
    const subs = c.subcriterios_evaluados!.map(s => s.id === subId ? { ...s, [field]: value } : s);
    const changedScore = field === 'puntaje_obtenido' && !Object.is(previous.puntaje_obtenido, value);
    const baseline = original?.find(item => item.id === criterioId);
    const restored = baseline && subs.every(s => {
      const saved = baseline.subcriterios_evaluados?.find(item => item.id === s.id);
      return saved && Number(saved.puntaje_obtenido) === s.puntaje_obtenido;
    });
    return { ...c, subcriterios_evaluados: subs,
      puntaje_obtenido: changedScore ? restored ? Number(baseline.puntaje_obtenido) : sumarPuntajes(subs.map(s => s.puntaje_obtenido)) : c.puntaje_obtenido };
  });
}

export function erroresSubcriterios(criterios: CriterioEvaluado[]): Record<string, string> {
  const errors: Record<string, string> = {};
  criterios.forEach(c => {
    c.subcriterios_evaluados?.forEach(s => {
      if (!Number.isFinite(s.puntaje_obtenido) || s.puntaje_obtenido < 0 || s.puntaje_obtenido > s.puntaje_maximo) {
        errors[`${c.id}/${s.id}`] = `El puntaje de ${s.id} debe estar entre 0 y ${s.puntaje_maximo}.`;
      } else if (!s.feedback.trim()) {
        errors[`${c.id}/${s.id}`] = `El subcriterio ${s.id} requiere un comentario.`;
      }
    });
    if ((c.subcriterios_evaluados?.length ?? 0) > 0 && c.puntaje_obtenido > c.puntaje_maximo) {
      errors[c.id] = `La suma de subcriterios supera el máximo de ${c.nombre}.`;
    }
  });
  return errors;
}
