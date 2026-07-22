import { describe, it, expect, vi, beforeEach } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';

// Mockeamos el apiClient para controlar qué devuelve/lanza cada request.
vi.mock('@/shared/services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

import { apiClient } from '@/shared/services/api-client';
import { getCorreccionByEntregaId } from './correcciones-service';

const mockGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

function makeAxiosError(status: number): AxiosError {
  const config: InternalAxiosRequestConfig = { headers: new AxiosHeaders() };
  const response: AxiosResponse = {
    status,
    statusText: '',
    data: { detail: 'boom' },
    headers: {},
    config,
  };
  return new AxiosError(`Request failed with status code ${status}`, 'ERR', config, undefined, response);
}

describe('getCorreccionByEntregaId (ERR-006: null SOLO en 404)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('devuelve la corrección cuando la request tiene éxito', async () => {
    const correccion = { id: 5, entrega_id: 42, nota: 8 };
    mockGet.mockResolvedValueOnce({ data: correccion });

    await expect(getCorreccionByEntregaId(42)).resolves.toEqual(correccion);
  });

  it('devuelve null cuando el backend responde 404 (no hay corrección todavía)', async () => {
    mockGet.mockRejectedValueOnce(makeAxiosError(404));

    await expect(getCorreccionByEntregaId(42)).resolves.toBeNull();
  });

  it('re-lanza el error cuando NO es 404 (500): no lo disfraza de "sin corrección"', async () => {
    const error = makeAxiosError(500);
    mockGet.mockRejectedValueOnce(error);

    await expect(getCorreccionByEntregaId(42)).rejects.toBe(error);
  });

  it('re-lanza errores que no son AxiosError (p. ej. red caída sin response)', async () => {
    const error = new Error('Network down');
    mockGet.mockRejectedValueOnce(error);

    await expect(getCorreccionByEntregaId(42)).rejects.toBe(error);
  });
});
