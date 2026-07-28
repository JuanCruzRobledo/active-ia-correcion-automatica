import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useState } from 'react';
import type { ReactNode } from 'react';
import { renderHook, act } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { TenantProvider } from './TenantProvider';
import { useTenant } from './useTenant';
import { switchUniversidad, AUTH_SESSION_EVENT } from '@/features/auth/services/auth-service';
import type { UserInfo } from '@/shared/types';

vi.mock('@/features/auth/services/auth-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/auth/services/auth-service')>();
  return { ...actual, switchUniversidad: vi.fn() };
});

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

function setSession(user: UserInfo, token = 'JWT') {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

let queryClient: QueryClient;

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function Wrapper({ children }: { children: ReactNode }) {
  // useState (no una variable de módulo reasignada en cada render): el wrapper
  // es un componente y RTL lo re-renderiza; sin esto cada render creaba un
  // QueryClient nuevo y "perdía" la caché entre renders.
  const [client] = useState(() => {
    queryClient = makeQueryClient();
    return queryClient;
  });
  return (
    <QueryClientProvider client={client}>
      <TenantProvider>{children}</TenantProvider>
    </QueryClientProvider>
  );
}

describe('useTenant / TenantProvider (D1: contexto reactivo sobre localStorage)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  it('el rol proviene de la membresía activa de la sesión vigente', () => {
    setSession(makeUser({ rol: 'COORDINADOR', universidad_activa_id: 8 }));

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });

    expect(result.current.rol).toBe('COORDINADOR');
    expect(result.current.universidadActivaId).toBe(8);
    expect(result.current.esSuperadmin).toBe(false);
  });

  it('sesión sin universidad activa: universidadActivaId y rol son null', () => {
    setSession(makeUser({ rol: null, universidad_activa_id: null, es_superadmin: true }));

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });

    expect(result.current.universidadActivaId).toBeNull();
    expect(result.current.rol).toBeNull();
    expect(result.current.esSuperadmin).toBe(true);
  });

  it('propagación sin recarga: al persistirse una nueva sesión (AUTH_SESSION_EVENT), el rol se actualiza', () => {
    setSession(makeUser({ rol: 'TUTOR', universidad_activa_id: 1 }));
    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });
    expect(result.current.rol).toBe('TUTOR');

    act(() => {
      setSession(makeUser({ rol: 'COORDINADOR', universidad_activa_id: 2 }));
      window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
    });

    expect(result.current.rol).toBe('COORDINADOR');
    expect(result.current.universidadActivaId).toBe(2);
  });

  it('cambiarUniversidad llama a switchUniversidad y limpia la caché con queryClient.clear() (D4)', async () => {
    setSession(makeUser({ rol: 'TUTOR', universidad_activa_id: 1 }));
    vi.mocked(switchUniversidad).mockImplementation(async (id) => {
      setSession(makeUser({ rol: 'COORDINADOR', universidad_activa_id: id ?? undefined as never }));
      window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
      return { access_token: 'JWT2', token_type: 'bearer', user: makeUser({ universidad_activa_id: 2 }) };
    });

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });
    const clearSpy = vi.spyOn(queryClient, 'clear');

    await act(async () => {
      await result.current.cambiarUniversidad(2);
    });

    expect(switchUniversidad).toHaveBeenCalledWith(2);
    expect(clearSpy).toHaveBeenCalledTimes(1);
  });

  it('cambiarUniversidad cancela las queries en vuelo ANTES de limpiar la caché (fix ventana de carrera D4)', async () => {
    setSession(makeUser({ rol: 'TUTOR', universidad_activa_id: 1 }));
    vi.mocked(switchUniversidad).mockImplementation(async (id) => {
      setSession(makeUser({ rol: 'COORDINADOR', universidad_activa_id: id ?? undefined as never }));
      window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
      return { access_token: 'JWT2', token_type: 'bearer', user: makeUser({ universidad_activa_id: 2 }) };
    });

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });

    const orden: string[] = [];
    vi.spyOn(queryClient, 'cancelQueries').mockImplementation(async () => {
      orden.push('cancelQueries');
    });
    vi.spyOn(queryClient, 'clear').mockImplementation(() => {
      orden.push('clear');
    });

    await act(async () => {
      await result.current.cambiarUniversidad(2);
    });

    // Sin cancelar primero, una respuesta tardía del tenant anterior podría
    // reescribirse en la caché ya "limpia" del tenant nuevo si el mismo query
    // key sigue montado — por eso el orden importa, no solo que ambas se llamen.
    expect(orden).toEqual(['cancelQueries', 'clear']);
  });

  it('switch fallido: NO llama a queryClient.clear() y la sesión anterior queda intacta', async () => {
    setSession(makeUser({ rol: 'TUTOR', universidad_activa_id: 1 }));
    vi.mocked(switchUniversidad).mockRejectedValue(new Error('403'));

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });
    const clearSpy = vi.spyOn(queryClient, 'clear');

    await expect(
      act(async () => {
        await result.current.cambiarUniversidad(99);
      })
    ).rejects.toThrow();

    expect(clearSpy).not.toHaveBeenCalled();
    expect(result.current.universidadActivaId).toBe(1);
  });

  it('escenario de filtración: datos cargados bajo la universidad A no quedan disponibles tras cambiar a B', async () => {
    // D4: la prueba clave es que `clear()` (no `invalidateQueries`) BORRA la
    // caché — con `invalidate` los datos viejos siguen siendo servidos por
    // `getQueryData` mientras revalida en background, que es exactamente la
    // filtración entre tenants que este requisito prohíbe. Se sembra la
    // caché directamente (sin un observer `useQuery` montado) para verificar
    // el efecto de `clear()` en sí mismo, sin la interferencia de un refetch
    // automático en paralelo.
    setSession(makeUser({ rol: 'TUTOR', universidad_activa_id: 1 }));
    vi.mocked(switchUniversidad).mockImplementation(async () => {
      setSession(makeUser({ rol: 'COORDINADOR', universidad_activa_id: 2 }));
      window.dispatchEvent(new Event(AUTH_SESSION_EVENT));
      return { access_token: 'JWT2', token_type: 'bearer', user: makeUser({ universidad_activa_id: 2 }) };
    });

    const { result } = renderHook(() => useTenant(), { wrapper: Wrapper });

    queryClient.setQueryData(['materias'], ['materia-de-A']);
    expect(queryClient.getQueryData(['materias'])).toEqual(['materia-de-A']);

    await act(async () => {
      await result.current.cambiarUniversidad(2);
    });

    // Tras el clear(), la caché ya no tiene los datos de A: ni el valor viejo
    // servido "mientras revalida" (eso es lo que haría invalidateQueries).
    expect(queryClient.getQueryData(['materias'])).toBeUndefined();
  });
});
