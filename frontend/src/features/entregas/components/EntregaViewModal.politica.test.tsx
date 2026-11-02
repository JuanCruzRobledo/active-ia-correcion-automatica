import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import EntregaViewModal from './EntregaViewModal';

const response = vi.hoisted(() => ({ data: {} as Record<string, unknown> }));
vi.mock('../hooks/useEntregas', () => ({
  useEntregaContenido: () => ({ ...response, isLoading: false, isError: false, error: null }),
}));

const content = {
  entrega_id: 1, alumno_nombre: 'Alumno', es_pdf: false,
  contenido_consolidado: 'fetch("/api/categorias");', pdf_contenido_b64: null,
  archivos_incluidos: ['src/api/client.js'], total_lineas: 1, total_caracteres: 25,
};
const analysis = {
  version: 1, archivos_incluidos: ['src/api/client.js'],
  archivos_ignorados: [
    { ruta: 'proyecto/.DS_Store', motivo: 'metadatos_o_lockfile' },
    { ruta: 'proyecto/node_modules/lib/index.js', motivo: 'dependencias_o_compilados' },
  ],
  rutas_penalizables: ['proyecto/node_modules/'], limite_nota: 50 as number | null,
  directorios_permitidos: [],
};

function openModal(analisis_archivos?: typeof analysis | null) {
  response.data = { ...content, analisis_archivos };
  return render(<EntregaViewModal entregaId={1} alumno="Alumno" archivoNombre="tp.zip" isOpen onClose={() => {}} />);
}

describe('EntregaViewModal — política de archivos', () => {
  it('explica el tope y muestra la ruta que debe quitarse de la reentrega', () => {
    openModal(analysis);
    expect(screen.getByText(/límite de nota por archivos no evaluables/i)).toBeInTheDocument();
    expect(screen.getByText('proyecto/node_modules/')).toBeInTheDocument();
    expect(screen.getByText(/máximo.*50.*100/i)).toBeInTheDocument();
    expect(screen.getByText(/nueva entrega.*sin estos archivos/i)).toBeInTheDocument();
  });

  it('informa residuos ignorados sin presentar un tope de nota', () => {
    openModal({
      ...analysis, archivos_ignorados: analysis.archivos_ignorados.slice(0, 1),
      rutas_penalizables: [], limite_nota: null,
    });
    expect(screen.getByText(/archivos ignorados sin penalización/i)).toBeInTheDocument();
    expect(screen.getByText('proyecto/.DS_Store')).toBeInTheDocument();
    expect(screen.queryByText(/límite de nota por archivos no evaluables/i)).not.toBeInTheDocument();
  });

  it('no presenta dependencias penalizables como residuos sin penalización', () => {
    openModal(analysis);
    expect(screen.queryByText(/archivos ignorados sin penalización/i)).not.toBeInTheDocument();
  });

  it('mantiene el visor de entregas anteriores sin inventar infracciones', () => {
    openModal(null);
    expect(screen.getByText('Archivos Incluidos')).toBeInTheDocument();
    expect(screen.queryByText(/límite de nota por archivos no evaluables/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/archivos ignorados sin penalización/i)).not.toBeInTheDocument();
  });
});
