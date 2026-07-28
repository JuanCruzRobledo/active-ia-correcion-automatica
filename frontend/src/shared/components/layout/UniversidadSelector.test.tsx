import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { UniversidadSelector } from './UniversidadSelector';
import { universidadesService } from '@/features/universidades/services/universidades-service';
import { useTenant } from '@/shared/context/useTenant';

const navigateMock = vi.fn();

vi.mock('react-hot-toast', () => ({ default: { success: vi.fn(), error: vi.fn() } }));
vi.mock('@/features/universidades/services/universidades-service', () => ({
  universidadesService: { getMias: vi.fn() },
}));
vi.mock('@/shared/context/useTenant', () => ({
  useTenant: vi.fn(),
}));
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

function renderSelector() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return render(<UniversidadSelector />, { wrapper });
}

describe('UniversidadSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('con dos universidades: muestra ambas y marca cuál es la activa', async () => {
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
      { id: 2, nombre: 'Otra Uni', rol: 'COORDINADOR' },
    ]);
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: 1,
      rol: 'TUTOR',
      esSuperadmin: false,
      cambiarUniversidad: vi.fn(),
    });

    renderSelector();
    fireEvent.click(await screen.findByRole('button'));

    expect(await screen.findByText('TUPaD')).toBeInTheDocument();
    expect(screen.getByText('Otra Uni')).toBeInTheDocument();
  });

  it('superadmin: ve todas las universidades activas MÁS la opción "Todas las universidades"', async () => {
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'ADMIN' },
      { id: 2, nombre: 'Otra Uni', rol: 'ADMIN' },
    ]);
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: null,
      rol: null,
      esSuperadmin: true,
      cambiarUniversidad: vi.fn(),
    });

    renderSelector();
    fireEvent.click(await screen.findByRole('button'));

    expect(await screen.findByText('Todas las universidades')).toBeInTheDocument();
    expect(screen.getByText('TUPaD')).toBeInTheDocument();
    expect(screen.getByText('Otra Uni')).toBeInTheDocument();
  });

  it('usuario no-superadmin con una sola universidad: no ofrece alternativas de cambio', async () => {
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
    ]);
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: 1,
      rol: 'TUTOR',
      esSuperadmin: false,
      cambiarUniversidad: vi.fn(),
    });

    renderSelector();

    expect(await screen.findByText('TUPaD')).toBeInTheDocument();
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('al elegir otra universidad, llama a cambiarUniversidad y navega a /dashboard', async () => {
    const cambiarUniversidad = vi.fn().mockResolvedValue(undefined);
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
      { id: 2, nombre: 'Otra Uni', rol: 'COORDINADOR' },
    ]);
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: 1,
      rol: 'TUTOR',
      esSuperadmin: false,
      cambiarUniversidad,
    });

    renderSelector();
    fireEvent.click(await screen.findByRole('button'));
    fireEvent.click(await screen.findByText('Otra Uni'));

    await waitFor(() => expect(cambiarUniversidad).toHaveBeenCalledWith(2));
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard'));
  });

  it('superadmin elige "Todas las universidades": llama a cambiarUniversidad con null', async () => {
    const cambiarUniversidad = vi.fn().mockResolvedValue(undefined);
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'ADMIN' },
    ]);
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: 1,
      rol: 'ADMIN',
      esSuperadmin: true,
      cambiarUniversidad,
    });

    renderSelector();
    fireEvent.click(await screen.findByRole('button'));
    fireEvent.click(await screen.findByText('Todas las universidades'));

    await waitFor(() => expect(cambiarUniversidad).toHaveBeenCalledWith(null));
  });
});
