import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UniversidadesPage } from './UniversidadesPage';
import { universidadesService } from '../services/universidades-service';
import type { UniversidadList } from '../types';

vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('../services/universidades-service', () => ({
  universidadesService: {
    getMias: vi.fn(),
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    remove: vi.fn(),
  },
}));

const listaActivas: UniversidadList = {
  items: [
    { id: 1, nombre: 'TUPaD', moodle_host: 'https://moodle.tupad.edu.ar', activa: true },
  ],
  total: 1,
  page: 1,
  per_page: 20,
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return render(<UniversidadesPage />, { wrapper });
}

describe('UniversidadesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(universidadesService.getAll).mockResolvedValue(listaActivas);
  });

  it('lista las universidades', async () => {
    renderPage();
    expect(await screen.findByText('TUPaD')).toBeInTheDocument();
    expect(screen.getByText('https://moodle.tupad.edu.ar')).toBeInTheDocument();
  });

  it('permite dar de alta una universidad', async () => {
    vi.mocked(universidadesService.create).mockResolvedValue({
      id: 2, nombre: 'Nueva Uni', moodle_host: null, activa: true,
      created_at: '', updated_at: '',
    });

    renderPage();
    await screen.findByText('TUPaD');

    fireEvent.click(screen.getByRole('button', { name: /nueva universidad/i }));
    fireEvent.change(screen.getByLabelText(/nombre/i), { target: { value: 'Nueva Uni' } });
    fireEvent.click(screen.getByRole('button', { name: /crear/i }));

    await waitFor(() =>
      expect(universidadesService.create).toHaveBeenCalledWith(
        expect.objectContaining({ nombre: 'Nueva Uni' })
      )
    );
  });

  it('permite editar una universidad', async () => {
    vi.mocked(universidadesService.update).mockResolvedValue({
      id: 1, nombre: 'TUPaD Renombrada', moodle_host: 'https://moodle.tupad.edu.ar',
      activa: true, created_at: '', updated_at: '',
    });

    renderPage();
    await screen.findByText('TUPaD');

    const acciones = await screen.findAllByLabelText(/acciones/i);
    fireEvent.click(acciones[0]);
    fireEvent.click(await screen.findByText('Editar'));

    const nombreInput = await screen.findByLabelText(/nombre/i);
    fireEvent.change(nombreInput, { target: { value: 'TUPaD Renombrada' } });
    fireEvent.click(screen.getByRole('button', { name: /guardar/i }));

    await waitFor(() =>
      expect(universidadesService.update).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ nombre: 'TUPaD Renombrada' })
      )
    );
  });

  it('permite dar de baja una universidad (baja lógica)', async () => {
    vi.mocked(universidadesService.remove).mockResolvedValue(undefined);

    renderPage();
    await screen.findByText('TUPaD');

    const acciones = await screen.findAllByLabelText(/acciones/i);
    fireEvent.click(acciones[0]);
    fireEvent.click(await screen.findByText('Dar de baja'));

    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: /dar de baja/i }));

    await waitFor(() => expect(universidadesService.remove).toHaveBeenCalledWith(1));
  });

  it('el toggle de inactivas pide el listado con include_inactive=true', async () => {
    renderPage();
    await screen.findByText('TUPaD');

    fireEvent.click(screen.getByRole('checkbox', { name: /mostrar inactivas/i }));

    await waitFor(() =>
      expect(universidadesService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ includeInactive: true })
      )
    );
  });
});
