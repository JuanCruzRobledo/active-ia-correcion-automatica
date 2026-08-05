import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));

vi.mock('../services/entregas-service', () => ({
  entregasService: { restore: vi.fn() },
}));

import { entregasService } from '../services/entregas-service';
import { useRestoreEntrega, entregasKeys } from './useEntregas';

const mockRestore = entregasService.restore as unknown as ReturnType<typeof vi.fn>;

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidate };
}

describe('useRestoreEntrega', () => {
  beforeEach(() => vi.clearAllMocks());

  it('restaura la entrega por su id', async () => {
    mockRestore.mockResolvedValueOnce({ id: 22279 });
    const { wrapper } = setup();

    const { result } = renderHook(() => useRestoreEntrega(), { wrapper });
    result.current.mutate(22279);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    // React Query v5 suma un segundo argumento de contexto al mutationFn, así que
    // se afirma sobre el primero y no sobre la lista completa.
    expect(mockRestore).toHaveBeenCalledTimes(1);
    expect(mockRestore.mock.calls[0][0]).toBe(22279);
  });

  it('invalida los listados para que la entrega restaurada reaparezca', async () => {
    mockRestore.mockResolvedValueOnce({ id: 5 });
    const { wrapper, invalidate } = setup();

    const { result } = renderHook(() => useRestoreEntrega(), { wrapper });
    result.current.mutate(5);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(invalidate).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: entregasKeys.lists() })
    );
  });

  it('propaga el error si el restore falla', async () => {
    mockRestore.mockRejectedValueOnce(new Error('boom'));
    const { wrapper } = setup();

    const { result } = renderHook(() => useRestoreEntrega(), { wrapper });
    result.current.mutate(9);

    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});
