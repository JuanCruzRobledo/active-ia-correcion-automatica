import { useState } from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { MetadataAdicionalEditor } from './MetadataAdicionalEditor';

function Form() {
  const [metadata, setMetadata] = useState<Record<string, unknown>>({
    lenguaje: 'Java', politica_entrega: { directorios_permitidos: ['dist'] },
  });
  return <>
    <MetadataAdicionalEditor metadata={metadata} onChange={setMetadata} />
    <output aria-label="Metadata guardada">{JSON.stringify(metadata)}</output>
  </>;
}

describe('MetadataAdicionalEditor', () => {
  it('no permite convertir la política de archivos en un campo de texto', () => {
    render(<Form />);
    expect(screen.getByDisplayValue('Java')).toBeInTheDocument();
    expect(screen.queryByDisplayValue('politica_entrega')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('[object Object]')).not.toBeInTheDocument();
  });

  it('preserva las excepciones al editar otro dato de la rúbrica', () => {
    render(<Form />);
    fireEvent.change(screen.getByDisplayValue('Java'), { target: { value: 'Kotlin' } });
    expect(JSON.parse(screen.getByLabelText('Metadata guardada').textContent ?? '')).toEqual({
      lenguaje: 'Kotlin', politica_entrega: { directorios_permitidos: ['dist'] },
    });
  });
});
