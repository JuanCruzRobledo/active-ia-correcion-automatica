import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useDeleteUsuario } from '../useUsuarios';
import { usuariosService } from '../../services/usuarios-service';

// El feedback de error del borrado (toast) es lo que se prueba: mockeamos el toast
// y el service para controlar el resultado de la mutación sin tocar la red.
vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../../services/usuarios-service', () => ({
  usuariosService: {
    delete: vi.fn(),
  },
}));

// Wrapper con un QueryClient de test (sin reintentos, para que el error/success
// se resuelva en un solo intento) reutilizable por cada caso.
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, queryClient };
};

describe('useDeleteUsuario', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra toast.error con el mensaje del backend cuando el borrado falla', async () => {
    vi.mocked(usuariosService.delete).mockRejectedValueOnce({
      detail: 'No podés eliminar al último administrador',
    });

    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useDeleteUsuario(), { wrapper });

    result.current.mutate(1);

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(toast.error).toHaveBeenCalledWith(
      'No podés eliminar al último administrador',
      { duration: 5000 }
    );
  });

  it('invalida las queries de usuarios y no muestra toast.error cuando el borrado es exitoso', async () => {
    vi.mocked(usuariosService.delete).mockResolvedValueOnce(undefined);

    const { wrapper, queryClient } = createWrapper();
    const invalidateSpy = vi.spyOn(queryClient, 'invalidateQueries');
    const { result } = renderHook(() => useDeleteUsuario(), { wrapper });

    result.current.mutate(5);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usuariosService.delete).toHaveBeenCalledWith(5);
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ['usuarios'] });
    expect(toast.error).not.toHaveBeenCalled();
  });
});
