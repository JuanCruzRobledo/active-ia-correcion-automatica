import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mockeamos el apiClient para controlar qué devuelve cada request (mismo patrón
// que correcciones-service.test.ts).
vi.mock('@/shared/services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

import { apiClient } from '@/shared/services/api-client';
import { login, seleccionarUniversidad, switchUniversidad, AUTH_SESSION_EVENT } from './auth-service';
import type { UserInfo, SeleccionUniversidadRequerida } from '@/shared/types';

const mockPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;

const TOKEN_KEY = 'auth_token';
const USER_KEY = 'auth_user';

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

describe('auth-service login() (Fase 5: unión discriminada por requiere_seleccion)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('con access_token: persiste token y usuario en localStorage', async () => {
    const user = makeUser();
    mockPost.mockResolvedValueOnce({
      data: { access_token: 'JWT', token_type: 'bearer', user },
    });

    const result = await login({ username: 'tutor1', password: 'x' });

    expect(result).toEqual({ access_token: 'JWT', token_type: 'bearer', user });
    expect(localStorage.getItem(TOKEN_KEY)).toBe('JWT');
    expect(JSON.parse(localStorage.getItem(USER_KEY)!)).toEqual(user);
  });

  it('con requiere_seleccion: NO persiste sesión ni lee user, y devuelve la lista de universidades', async () => {
    const seleccion: SeleccionUniversidadRequerida = {
      requiere_seleccion: true,
      universidades: [
        { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
        { id: 2, nombre: 'Otra', rol: 'COORDINADOR' },
      ],
      token_transicion: 'tok-transicion',
    };
    mockPost.mockResolvedValueOnce({ data: seleccion });

    const result = await login({ username: 'multiuni', password: 'x' });

    expect(result).toEqual(seleccion);
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(USER_KEY)).toBeNull();
  });

  it('la rama de selección nunca escribe el literal "undefined" en auth_token', async () => {
    const seleccion: SeleccionUniversidadRequerida = {
      requiere_seleccion: true,
      universidades: [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }],
      token_transicion: 'tok-transicion',
    };
    mockPost.mockResolvedValueOnce({ data: seleccion });

    await login({ username: 'multiuni', password: 'x' });

    expect(localStorage.getItem(TOKEN_KEY)).not.toBe('undefined');
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});

describe('auth-service seleccionarUniversidad()', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('llama a /auth/select-universidad con el token de transición y persiste el token final', async () => {
    const user = makeUser({ universidad_activa_id: 9, rol: 'COORDINADOR' });
    mockPost.mockResolvedValueOnce({
      data: { access_token: 'JWT-FINAL', token_type: 'bearer', user },
    });

    const result = await seleccionarUniversidad('tok-transicion', 9);

    expect(mockPost).toHaveBeenCalledWith(
      '/auth/select-universidad',
      { universidad_id: 9 },
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer tok-transicion' }),
      })
    );
    expect(result.access_token).toBe('JWT-FINAL');
    expect(localStorage.getItem(TOKEN_KEY)).toBe('JWT-FINAL');
    expect(JSON.parse(localStorage.getItem(USER_KEY)!)).toEqual(user);
  });
});

describe('auth-service switchUniversidad() + AUTH_SESSION_EVENT (D1: reactividad de TenantProvider)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('llama a /auth/switch-universidad, persiste el token y dispara AUTH_SESSION_EVENT', async () => {
    const user = makeUser({ universidad_activa_id: 3, rol: 'ADMIN' });
    mockPost.mockResolvedValueOnce({
      data: { access_token: 'JWT-SWITCH', token_type: 'bearer', user },
    });
    const listener = vi.fn();
    window.addEventListener(AUTH_SESSION_EVENT, listener);

    const result = await switchUniversidad(3);

    expect(mockPost).toHaveBeenCalledWith('/auth/switch-universidad', { universidad_id: 3 });
    expect(result.access_token).toBe('JWT-SWITCH');
    expect(localStorage.getItem(TOKEN_KEY)).toBe('JWT-SWITCH');
    expect(listener).toHaveBeenCalledTimes(1);

    window.removeEventListener(AUTH_SESSION_EVENT, listener);
  });

  it('modo global del superadmin: acepta universidad_id null', async () => {
    const user = makeUser({ universidad_activa_id: null, rol: null, es_superadmin: true });
    mockPost.mockResolvedValueOnce({
      data: { access_token: 'JWT-GLOBAL', token_type: 'bearer', user },
    });

    await switchUniversidad(null);

    expect(mockPost).toHaveBeenCalledWith('/auth/switch-universidad', { universidad_id: null });
  });

  it('login() también dispara AUTH_SESSION_EVENT cuando persiste sesión', async () => {
    const user = makeUser();
    mockPost.mockResolvedValueOnce({
      data: { access_token: 'JWT', token_type: 'bearer', user },
    });
    const listener = vi.fn();
    window.addEventListener(AUTH_SESSION_EVENT, listener);

    await login({ username: 'tutor1', password: 'x' });

    expect(listener).toHaveBeenCalledTimes(1);
    window.removeEventListener(AUTH_SESSION_EVENT, listener);
  });
});
