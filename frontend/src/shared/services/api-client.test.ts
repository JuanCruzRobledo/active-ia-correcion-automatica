import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import toast from 'react-hot-toast';
import { handleResponseError } from './api-client';

// El interceptor dispara toasts vía react-hot-toast; lo mockeamos para espiarlo.
vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));

/**
 * Construye un AxiosError realista (con `config.url`, `response.status` y
 * `response.data.detail`) para ejercitar `handleResponseError` directamente,
 * sin depender de los internals del interceptor de axios.
 */
function makeAxiosError(
  status: number,
  url: string,
  detail: string
): AxiosError<{ detail?: string }> {
  const config: InternalAxiosRequestConfig = {
    url,
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

// window.location.href se muta en la rama de sesión expirada; lo reemplazamos por
// un objeto plano para poder afirmar la redirección sin que jsdom navegue.
const originalLocation = window.location;

describe('handleResponseError (interceptor de response de axios)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
    localStorage.clear();
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: { href: '' },
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    Object.defineProperty(window, 'location', {
      configurable: true,
      writable: true,
      value: originalLocation,
    });
  });

  it('401 en /auth/login: preserva el error, sin toast ni logout ni redirect', async () => {
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem');
    const error = makeAxiosError(
      401,
      '/auth/login',
      'Credenciales inválidas. 2 intentos restantes.'
    );

    // La promesa se rechaza con el MISMO error (mensaje real preservado).
    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).not.toHaveBeenCalled();
    expect(removeItem).not.toHaveBeenCalled();

    // Ni siquiera tras avanzar el tiempo hay redirección.
    vi.advanceTimersByTime(2000);
    expect(window.location.href).toBe('');
  });

  it('401 en /entregas: toast "Sesión expirada", limpia sesión y redirige (TRIANGULATE)', async () => {
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem');
    const error = makeAxiosError(401, '/entregas', 'Not authenticated');

    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith(
      'Sesión expirada. Por favor, inicia sesión nuevamente.'
    );
    expect(removeItem).toHaveBeenCalledWith('auth_token');
    expect(removeItem).toHaveBeenCalledWith('auth_user');

    // El redirect ocurre tras 1.5s.
    expect(window.location.href).toBe('');
    vi.advanceTimersByTime(1500);
    expect(window.location.href).toBe('/login');
  });

  it('403: muestra el mensaje del backend sin tocar la sesión (no regresión)', async () => {
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem');
    const error = makeAxiosError(403, '/materias', 'No tienes permisos.');

    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith('No tienes permisos.');
    expect(removeItem).not.toHaveBeenCalled();
    vi.advanceTimersByTime(2000);
    expect(window.location.href).toBe('');
  });

  it('422: muestra el mensaje de validación sin tocar la sesión (no regresión)', async () => {
    const removeItem = vi.spyOn(Storage.prototype, 'removeItem');
    const error = makeAxiosError(422, '/usuarios', 'Datos inválidos.');

    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith('Datos inválidos.');
    expect(removeItem).not.toHaveBeenCalled();
  });

  it('500: muestra el mensaje de error del servidor (no regresión)', async () => {
    const error = makeAxiosError(500, '/correcciones', 'Boom interno.');

    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith('Boom interno.');
  });

  it('error de red (sin response): muestra el toast de conexión (no regresión)', async () => {
    const error = new AxiosError<{ detail?: string }>('Network Error', 'ERR_NETWORK');

    await expect(handleResponseError(error)).rejects.toBe(error);

    expect(toast.error).toHaveBeenCalledWith(
      'Error de conexión. Verifica tu conexión a internet.'
    );
  });
});
