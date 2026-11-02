import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import CorreccionViewEditModal from './CorreccionViewEditModal';
import type { Correccion } from '../types';

vi.mock('../hooks/useCorrecciones', () => ({
  useUpdateCorreccion: () => ({ mutate: vi.fn(), isPending: false }),
}));

const correction: Correccion & {
  nota_academica?: number | null;
  limite_nota?: number | null;
  rutas_penalizables?: string[];
} = {
  id: 1, entrega_id: 1, nota: 50, nota_antes_penalizaciones: null,
  condicion_desaprobacion_aplicada: null, condicion_desaprobacion_descripcion: null,
  penalizaciones_aplicadas: [], penalizaciones_descripciones: [], criterios: [],
  fortalezas: [], recomendaciones: [], comentario_general: 'Trabajo evaluado.',
  editado_manualmente: false, fecha_correccion: '2026-10-30T12:00:00Z',
  nota_academica: 82, limite_nota: 50, rutas_penalizables: ['tp/dist/'],
};

function openModal(data = correction) {
  return render(<CorreccionViewEditModal correccion={data} alumno="Alumno" trabajoNombre="TP" isOpen onClose={() => {}} />);
}

describe('CorreccionViewEditModal — tope posterior a evaluación', () => {
  it('distingue la nota académica de la final y explica el tope', () => {
    openModal();
    expect(screen.getByText(/nota académica/i)).toBeInTheDocument();
    expect(screen.getByText('82.0')).toBeInTheDocument();
    expect(screen.getByText(/máximo.*50.*100/i)).toBeInTheDocument();
    expect(screen.getByText('tp/dist/')).toBeInTheDocument();
  });

  it('muestra la restricción aunque la nota académica sea inferior al tope', () => {
    openModal({ ...correction, nota: 35, nota_academica: 35 });
    expect(screen.getByText(/máximo.*50.*100/i)).toBeInTheDocument();
    expect(screen.getAllByText('35.0')).toHaveLength(2);
  });

  it('no muestra una restricción en la corrección de una entrega limpia', () => {
    openModal({ ...correction, nota: 82, nota_academica: 82, limite_nota: null, rutas_penalizables: [] });
    expect(screen.queryByText(/límite de nota por archivos no evaluables/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/máximo.*50.*100/i)).not.toBeInTheDocument();
  });

  it('edita la nota académica para no reemplazarla por el tope al guardar', () => {
    openModal();
    fireEvent.click(screen.getByRole('button', { name: /editar/i }));
    expect(screen.getByRole('spinbutton')).toHaveValue(82);
  });
});
