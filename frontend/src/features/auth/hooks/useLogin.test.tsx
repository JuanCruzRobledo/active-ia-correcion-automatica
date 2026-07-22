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

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));
vi.mock('../services/auth-service');

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
