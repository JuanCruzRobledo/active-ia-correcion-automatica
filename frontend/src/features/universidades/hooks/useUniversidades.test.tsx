import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useUniversidadesMias, useUniversidades, useCreateUniversidad } from './useUniversidades';
import { universidadesService } from '../services/universidades-service';

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

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

describe('useUniversidadesMias', () => {
  beforeEach(() => vi.clearAllMocks());

  it('trae las universidades propias del usuario', async () => {
    vi.mocked(universidadesService.getMias).mockResolvedValue([
      { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
    ]);

    const { result } = renderHook(() => useUniversidadesMias(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual([{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }]);
  });
});

describe('useUniversidades (ABM)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('trae el listado paginado', async () => {
    vi.mocked(universidadesService.getAll).mockResolvedValue({
      items: [{ id: 1, nombre: 'TUPaD', moodle_host: null, activa: true }],
      total: 1,
      page: 1,
      per_page: 20,
    });

    const { result } = renderHook(() => useUniversidades({}), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.total).toBe(1);
  });
});

describe('useCreateUniversidad', () => {
  beforeEach(() => vi.clearAllMocks());

  it('crea y muestra un toast de éxito', async () => {
    vi.mocked(universidadesService.create).mockResolvedValue({
      id: 5, nombre: 'Nueva', moodle_host: null, activa: true, created_at: '', updated_at: '',
    });

    const { result } = renderHook(() => useCreateUniversidad(), { wrapper });
    result.current.mutate({ nombre: 'Nueva' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(toast.success).toHaveBeenCalled();
  });
});
