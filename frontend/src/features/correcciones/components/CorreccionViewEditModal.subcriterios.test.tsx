import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CorreccionViewEditModal from './CorreccionViewEditModal';
import type { Correccion, CorreccionUpdate } from '../types';

const mutation = vi.hoisted(() => ({ mutate: vi.fn(), isPending: false }));
vi.mock('../hooks/useCorrecciones', () => ({ useUpdateCorreccion: () => mutation }));
const correction: Correccion = {
  id: 1, entrega_id: 1, nota: 50, nota_academica: 82, limite_nota: 50,
  rutas_penalizables: ['tp/dist/'], nota_antes_penalizaciones: null,
  condicion_desaprobacion_aplicada: null, condicion_desaprobacion_descripcion: null,
  penalizaciones_aplicadas: [], penalizaciones_descripciones: [],
  criterios: [{ id: 'C1', nombre: 'Funcionalidad', puntaje_obtenido: 30, puntaje_maximo: 100,
    estado: 'WARNING', feedback: 'Comentario padre', subcriterios_evaluados: [
      { id: 'C1.1', puntaje_obtenido: 12, puntaje_maximo: 20, estado: 'WARNING', feedback: 'Original' },
      { id: 'C1.2', puntaje_obtenido: 18, puntaje_maximo: 80, estado: 'OK', feedback: 'Hermano' },
    ] }], fortalezas: [], recomendaciones: [], comentario_general: 'Trabajo evaluado.',
  editado_manualmente: false, fecha_correccion: '2026-10-30T12:00:00Z',
};
function open(data = correction, onClose = vi.fn()) {
  return render(<CorreccionViewEditModal correccion={data} alumno="Alumno" trabajoNombre="TP" isOpen onClose={onClose} />);
}
const edit = () => fireEvent.click(screen.getByRole('button', { name: /^editar$/i }));
const score = () => screen.getByRole('spinbutton', { name: 'Puntaje C1.1' });
const comment = () => screen.getByRole('textbox', { name: 'Comentario C1.1' });
const save = () => screen.getByRole('button', { name: /guardar cambios/i });
const payload = () => mutation.mutate.mock.calls[0][0].data as CorreccionUpdate;

beforeEach(() => { mutation.mutate.mockReset(); mutation.isPending = false; });
describe('edición manual de subcriterios', () => {
  it('consulta sin controles editables y permite editar puntaje/comentario', () => {
    open(); expect(screen.queryByRole('spinbutton', { name: 'Puntaje C1.1' })).not.toBeInTheDocument();
    edit(); expect(score()).toHaveValue(12); expect(comment()).toHaveValue('Original');
    expect(screen.queryByRole('combobox', { name: 'Puntaje C1' })).not.toBeInTheDocument();
  });
  it('guarda desglose completo, deriva padre y conserva nota académica sin Recalcular', () => {
    open(); edit(); fireEvent.change(score(), { target: { value: '16' } });
    fireEvent.change(comment(), { target: { value: 'Corregido' } }); fireEvent.click(save());
    expect(payload().nota).toBe(82); expect(payload().nota_antes_penalizaciones).toBe(34);
    expect(payload().criterios![0]).toMatchObject({ puntaje_obtenido: 34, estado: 'WARNING', feedback: 'Comentario padre' });
    expect(payload().criterios![0].subcriterios_evaluados).toEqual([
      { ...correction.criterios[0].subcriterios_evaluados![0], puntaje_obtenido: 16, feedback: 'Corregido' },
      correction.criterios[0].subcriterios_evaluados![1],
    ]);
    expect(correction.criterios[0].subcriterios_evaluados![0].puntaje_obtenido).toBe(12);
  });
  it('Recalcular conserva académica 82 y permite que servidor aplique final 50', () => {
    open(); edit(); fireEvent.change(screen.getByRole('spinbutton', { name: 'Puntaje C1.2' }), { target: { value: '70' } });
    fireEvent.click(screen.getByRole('button', { name: /^recalcular$/i })); fireEvent.click(save());
    expect(payload().nota).toBe(82); expect(payload().criterios![0].puntaje_obtenido).toBe(82);
    expect(screen.getByText(/máximo.*50.*100/i)).toBeInTheDocument();
  });
  it('solo feedback preserva padre histórico y nota anterior', () => {
    open({ ...correction, criterios: [{ ...correction.criterios[0], puntaje_obtenido: 90 }] }); edit();
    fireEvent.change(comment(), { target: { value: 'Texto nuevo' } }); fireEvent.click(save());
    expect(payload().criterios![0].puntaje_obtenido).toBe(90); expect(payload().nota).toBe(82);
  });
  it.each(['-1', '21', ''])('bloquea puntaje inválido %s', value => {
    open(); edit(); fireEvent.change(score(), { target: { value } });
    expect(save()).toBeDisabled(); expect(screen.getByText(/puntaje de C1.1 debe/i)).toBeInTheDocument();
  });
  it.each(['', '   '])('bloquea comentario vacío %s', value => {
    open(); edit(); fireEvent.change(comment(), { target: { value } }); expect(save()).toBeDisabled();
    expect(screen.getByText(/C1.1 requiere un comentario/i)).toBeInTheDocument();
  });
  it.each(['0', '20', '2.5'])('acepta límites y decimales %s', value => {
    open(); edit(); fireEvent.change(score(), { target: { value } }); expect(save()).not.toBeDisabled();
    fireEvent.click(save()); expect(payload().criterios![0].subcriterios_evaluados![0].puntaje_obtenido).toBe(Number(value));
  });
  it('cancelar restaura copia original y no guarda', () => {
    open(); edit(); fireEvent.change(score(), { target: { value: '16' } });
    fireEvent.click(screen.getByRole('button', { name: /^cancelar$/i })); edit();
    expect(score()).toHaveValue(12); expect(mutation.mutate).not.toHaveBeenCalled();
  });
  it('cerrar y reabrir o cambiar corrección descarta borrador', () => {
    const onClose = vi.fn(); const view = open(correction, onClose); edit();
    fireEvent.change(comment(), { target: { value: 'Borrador' } });
    fireEvent.click(screen.getByRole('button', { name: /cerrar/i })); expect(onClose).toHaveBeenCalled();
    view.rerender(<CorreccionViewEditModal correccion={correction} alumno="Alumno" trabajoNombre="TP" isOpen onClose={onClose} />);
    edit(); expect(comment()).toHaveValue('Original');
    view.rerender(<CorreccionViewEditModal correccion={{ ...correction, id: 2 }} alumno="Otro" trabajoNombre="TP" isOpen onClose={onClose} />);
    edit(); expect(comment()).toHaveValue('Original');
  });
  it('guardado fallido conserva borrador y pending bloquea guardar', () => {
    open(); edit(); fireEvent.change(comment(), { target: { value: 'Borrador' } }); fireEvent.click(save());
    expect(comment()).toHaveValue('Borrador');
    // A failed mutation never calls onSuccess: the draft and edit mode remain intact.
    expect(save()).toBeInTheDocument();
  });
  it('mutación pendiente impide otro guardado', () => {
    const view = open(); edit(); fireEvent.click(save()); mutation.isPending = true;
    view.rerender(<CorreccionViewEditModal correccion={correction} alumno="Alumno" trabajoNombre="TP" isOpen onClose={() => {}} />);
    expect(save()).toBeDisabled(); expect(score()).toBeDisabled(); expect(comment()).toBeDisabled();
    expect(screen.getByRole('button', { name: /^cancelar$/i })).toBeDisabled();
  });
  it.each([undefined, null, []])('sin desglose %s conserva editor del criterio', subs => {
    open({ ...correction, criterios: [{ ...correction.criterios[0], subcriterios_evaluados: subs }] }); edit();
    expect(screen.getByRole('combobox', { name: 'Puntaje C1' })).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton', { name: 'Puntaje C1.1' })).not.toBeInTheDocument();
  });
  it('una lectura posterior muestra cambios persistidos', () => {
    const view = open(); edit(); fireEvent.change(comment(), { target: { value: 'Guardado' } }); fireEvent.click(save());
    view.rerender(<CorreccionViewEditModal correccion={{ ...correction, criterios: payload().criterios! }} alumno="Alumno" trabajoNombre="TP" isOpen onClose={() => {}} />);
    expect(screen.getByText('Guardado')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Comentario C1.1' })).not.toBeInTheDocument();
  });
  it('normaliza puntajes anidados Decimal recibidos como texto sin alterar el snapshot', () => {
    const data = structuredClone(correction);
    data.criterios[0].subcriterios_evaluados![0].puntaje_obtenido = '2.5' as unknown as number;
    data.criterios[0].subcriterios_evaluados![0].puntaje_maximo = '20' as unknown as number;
    open(data); edit(); expect(score()).toHaveValue(2.5);
    fireEvent.change(score(), { target: { value: '3.5' } }); fireEvent.click(save());
    expect(payload().criterios![0].puntaje_obtenido).toBe(21.5);
    expect(data.criterios[0].subcriterios_evaluados![0].puntaje_obtenido).toBe('2.5');
  });
  it('cerrar desde props y volver a abrir restaura el modo consulta', () => {
    const view = open(); edit(); fireEvent.change(comment(), { target: { value: 'Temporal' } });
    view.rerender(<CorreccionViewEditModal correccion={correction} alumno="Alumno" trabajoNombre="TP" isOpen={false} onClose={() => {}} />);
    view.rerender(<CorreccionViewEditModal correccion={correction} alumno="Alumno" trabajoNombre="TP" isOpen onClose={() => {}} />);
    edit(); expect(comment()).toHaveValue('Original'); expect(mutation.mutate).not.toHaveBeenCalled();
  });
  it.each(['16', ''])('restaura padre histórico al volver puntaje %s al original', intermediate => {
    open({ ...correction, criterios: [{ ...correction.criterios[0], puntaje_obtenido: 90 }] }); edit();
    fireEvent.change(score(), { target: { value: intermediate } });
    fireEvent.change(score(), { target: { value: '12' } }); fireEvent.click(save());
    expect(payload().criterios![0].puntaje_obtenido).toBe(90);
  });
});
