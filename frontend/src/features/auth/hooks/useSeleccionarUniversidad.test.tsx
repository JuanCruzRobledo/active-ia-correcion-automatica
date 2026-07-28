import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useSeleccionarUniversidad } from './useSeleccionarUniversidad';
import { seleccionarUniversidad } from '../services/auth-service';
import type { UserInfo } from '@/shared/types';

const navigateMock = vi.fn();

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));
vi.mock('../services/auth-service');
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

function makeUser(over: Partial<UserInfo> = {}): UserInfo {
  return {
    id: 1,
    username: 'multiuni',
    nombre: 'Multi Uni',
    rol: 'COORDINADOR',
    primer_login: false,
    gemini_api_key_valid: false,
    universidad_activa_id: 9,
    es_superadmin: false,
    ...over,
  };
}

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('useSeleccionarUniversidad', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('al elegir universidad, completa el login: toast de bienvenida y navega a /dashboard', async () => {
    const user = makeUser();
    vi.mocked(seleccionarUniversidad).mockResolvedValue({
      access_token: 'JWT-FINAL',
      token_type: 'bearer',
      user,
    });

    const { result } = renderHook(() => useSeleccionarUniversidad(), { wrapper });
    result.current.mutate({ tokenTransicion: 'tok-transicion', universidadId: 9 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(seleccionarUniversidad).toHaveBeenCalledWith('tok-transicion', 9);
    expect(toast.success).toHaveBeenCalledWith('¡Bienvenido, Multi Uni!');
    expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true });
  });

  it('con primer_login: navega a /change-password en vez de /dashboard', async () => {
    const user = makeUser({ primer_login: true });
    vi.mocked(seleccionarUniversidad).mockResolvedValue({
      access_token: 'JWT-FINAL',
      token_type: 'bearer',
      user,
    });

    const { result } = renderHook(() => useSeleccionarUniversidad(), { wrapper });
    result.current.mutate({ tokenTransicion: 'tok-transicion', universidadId: 9 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(navigateMock).toHaveBeenCalledWith('/change-password', { replace: true });
  });
});
