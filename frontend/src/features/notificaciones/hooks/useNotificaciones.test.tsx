import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import toast from 'react-hot-toast';
import { useDispararCorrida, useSetNotifConfig } from './useNotificaciones';
import { notificacionesService } from '../services/notificaciones.service';

// UI-003: la corrida de emails y el guardado de config deben notificar SIEMPRE que fallan.
vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock('../services/notificaciones.service', () => ({
  notificacionesService: {
    dispararCorrida: vi.fn(),
    setConfig: vi.fn(),
  },
}));

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return wrapper;
};

function axiosErrorWithDetail(detail: string): AxiosError {
  const config: InternalAxiosRequestConfig = { headers: new AxiosHeaders() };
  const response: AxiosResponse = {
    status: 500,
    statusText: '',
    data: { detail },
    headers: {},
    config,
  };
  return new AxiosError('Request failed with status code 500', 'ERR', config, undefined, response);
}

describe('useDispararCorrida / useSetNotifConfig (UI-003: onError con toast)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('dispararCorrida: toastea el detail del backend cuando falla', async () => {
    vi.mocked(notificacionesService.dispararCorrida).mockRejectedValueOnce(
      axiosErrorWithDetail('SMTP caído: no se pudo enviar')
    );

    const { result } = renderHook(() => useDispararCorrida(), { wrapper: createWrapper() });
    result.current.mutate({ refrescar: false, incluirAlumnos: false, incluirNexos: true, comisiones: [] });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith('SMTP caído: no se pudo enviar');
  });

  it('dispararCorrida: usa el fallback cuando el error no trae detail', async () => {
    vi.mocked(notificacionesService.dispararCorrida).mockRejectedValueOnce(new Error('network'));

    const { result } = renderHook(() => useDispararCorrida(), { wrapper: createWrapper() });
    result.current.mutate({ refrescar: false, incluirAlumnos: false, incluirNexos: true, comisiones: [] });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith(
      'No se pudo disparar la corrida de emails. Revisá la conexión e intentá de nuevo.'
    );
  });

  it('setConfig: toastea al fallar el guardado de la config del cron', async () => {
    vi.mocked(notificacionesService.setConfig).mockRejectedValueOnce(new Error('boom'));

    const { result } = renderHook(() => useSetNotifConfig(), { wrapper: createWrapper() });
    result.current.mutate({} as never);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(toast.error).toHaveBeenCalledWith(
      'No se pudo guardar la configuración. Intentá nuevamente.'
    );
  });
});
