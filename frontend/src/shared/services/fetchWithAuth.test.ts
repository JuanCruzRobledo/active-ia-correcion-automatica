import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { fetchWithAuth } from './fetchWithAuth';
import { apiClient } from './api-client';

describe('fetchWithAuth (ARCH-011: fetch autenticado compartido)', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal('fetch', fetchMock);
    fetchMock.mockResolvedValue(new Response('ok'));
    localStorage.clear();
    apiClient.defaults.baseURL = '/api/v1';
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  function headersOf(): Headers {
    return fetchMock.mock.calls[0][1].headers as Headers;
  }

  it('con token: antepone la baseURL y agrega el header Authorization', async () => {
    localStorage.setItem('auth_token', 'jwt-123');

    await fetchWithAuth('/por-entregar/entregar/stream', { method: 'POST' });

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/por-entregar/entregar/stream');
    expect(init.method).toBe('POST');
    expect(headersOf().get('Authorization')).toBe('Bearer jwt-123');
  });

  it('sin token: NO manda el header Authorization (comportamiento preservado)', async () => {
    await fetchWithAuth('/notificaciones/preview/alumno');

    expect(headersOf().has('Authorization')).toBe(false);
  });

  it('preserva los headers de init (p. ej. Content-Type) y los combina con auth', async () => {
    localStorage.setItem('auth_token', 'jwt-xyz');

    await fetchWithAuth('/moodle/importar/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ a: 1 }),
    });

    const headers = headersOf();
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('Authorization')).toBe('Bearer jwt-xyz');
    expect(fetchMock.mock.calls[0][1].body).toBe(JSON.stringify({ a: 1 }));
  });

  it('reenvía el AbortSignal de init', async () => {
    const controller = new AbortController();

    await fetchWithAuth('/gestion/dashboard/snapshot/stream', { signal: controller.signal });

    expect(fetchMock.mock.calls[0][1].signal).toBe(controller.signal);
  });
});
