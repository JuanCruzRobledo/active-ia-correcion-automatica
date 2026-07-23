import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import toast from 'react-hot-toast';
import { useLogin } from './useLogin';
import { login } from '../services/auth-service';
import type { UserInfo, SeleccionUniversidadRequerida } from '@/shared/types';

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
    username: 'tutor1',
    nombre: 'Tutor Uno',
    rol: 'TUTOR',
    primer_login: false,
    gemini_api_key_valid: false,
    universidad_activa_id: 7,
    es_superadmin: false,
    ...over,
  };
}

function makeAxiosError(status: number, detail: string): AxiosError<{ detail?: string }> {
  const config: InternalAxiosRequestConfig = {
    url: '/auth/login',
    headers: new AxiosHeaders(),
  };
  const response: AxiosResponse<{ detail?: string }> = {
    status,
    statusText: '',
    data: { detail },
    headers: {},
    config,
  };
  return new AxiosError<{ detail?: string }>(
    `Request failed with status code ${status}`,
    'ERR_BAD_REQUEST',
    config,
    undefined,
    response
  );
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

describe('useLogin onError', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('surfacea el mensaje real del backend ante un 401 de credenciales', async () => {
    vi.mocked(login).mockRejectedValue(
      makeAxiosError(401, 'Credenciales inválidas. 2 intentos restantes.')
    );

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ username: 'ana', password: 'mala' });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(toast.error).toHaveBeenCalledWith(
      'Credenciales inválidas. 2 intentos restantes.'
    );
  });

  it('no duplica el toast para un 403 (lo notifica el interceptor)', async () => {
    vi.mocked(login).mockRejectedValue(
      makeAxiosError(403, 'Cuenta bloqueada temporalmente.')
    );

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ username: 'ana', password: 'x' });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(toast.error).not.toHaveBeenCalled();
  });
});

describe('useLogin onSuccess', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('con access_token: muestra el toast de bienvenida y navega a /dashboard', async () => {
    const user = makeUser();
    vi.mocked(login).mockResolvedValue({ access_token: 'JWT', token_type: 'bearer', user });

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ username: 'tutor1', password: 'x' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(toast.success).toHaveBeenCalledWith('¡Bienvenido, Tutor Uno!');
    expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true });
  });

  it('con access_token y primer_login: navega a /change-password', async () => {
    const user = makeUser({ primer_login: true });
    vi.mocked(login).mockResolvedValue({ access_token: 'JWT', token_type: 'bearer', user });

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ username: 'tutor1', password: 'x' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(navigateMock).toHaveBeenCalledWith('/change-password', { replace: true });
  });

  it('con requiere_seleccion: NO navega ni muestra el toast de bienvenida', async () => {
    const seleccion: SeleccionUniversidadRequerida = {
      requiere_seleccion: true,
      universidades: [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }],
      token_transicion: 'tok-transicion',
    };
    vi.mocked(login).mockResolvedValue(seleccion);

    const { result } = renderHook(() => useLogin(), { wrapper });
    result.current.mutate({ username: 'multiuni', password: 'x' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(navigateMock).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  });
});
