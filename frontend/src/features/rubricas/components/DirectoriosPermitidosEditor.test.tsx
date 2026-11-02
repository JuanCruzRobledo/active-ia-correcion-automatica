import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { DirectoriosPermitidosEditor } from './DirectoriosPermitidosEditor';

function Form({ initial = {} }: { initial?: Record<string, unknown> }) {
  const [metadata, setMetadata] = useState<Record<string, unknown>>(initial);
  return <>
    <DirectoriosPermitidosEditor metadata={metadata} onChange={setMetadata} />
    <output aria-label="Metadata guardada">{JSON.stringify(metadata)}</output>
  </>;
}

describe('DirectoriosPermitidosEditor', () => {
  it('permite exceptuar dist sin perder otras configuraciones de la rúbrica', () => {
    render(<Form initial={{ lenguaje: 'Java', politica_entrega: { otra_regla: true } }} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'dist/' }));
    expect(JSON.parse(screen.getByLabelText('Metadata guardada').textContent ?? '')).toEqual({
      lenguaje: 'Java', politica_entrega: { otra_regla: true, directorios_permitidos: ['dist'] },
    });
    expect(screen.getByRole('checkbox', { name: 'dist/' })).toBeChecked();
  });

  it('retira una excepción sin eliminar las otras', () => {
    render(<Form initial={{ politica_entrega: { directorios_permitidos: ['dist', 'build'] } }} />);
    fireEvent.click(screen.getByRole('checkbox', { name: 'dist/' }));
    expect(screen.getByRole('checkbox', { name: 'dist/' })).not.toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'build/' })).toBeChecked();
    expect(JSON.parse(screen.getByLabelText('Metadata guardada').textContent ?? '')).toEqual({
      politica_entrega: { directorios_permitidos: ['build'] },
    });
  });

  it('no exceptúa carpetas por defecto y explica cuándo usar la excepción', () => {
    render(<Form />);
    expect(screen.queryAllByRole('checkbox', { checked: true })).toHaveLength(0);
    expect(screen.getByText(/solo.*consigna.*solicita/i)).toBeInTheDocument();
  });
});
