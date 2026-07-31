import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/shared/services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '@/shared/services/api-client';
import { rubricasService } from './rubricas-service';
import type { RubricaListItem } from '../types';

const mockGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;

/** Item mínimo: al servicio solo le importa el id para armar la lista completa. */
const item = (id: number) => ({ id }) as RubricaListItem;

describe('rubricasService.getAllPages', () => {
  beforeEach(() => vi.clearAllMocks());

  it('pide per_page=100 y devuelve la única página cuando todo entra en una', async () => {
    mockGet.mockResolvedValueOnce({
      data: { items: [item(1), item(2)], total: 2, page: 1, per_page: 100 },
    });

    const result = await rubricasService.getAllPages({ materia_id: 7 });

    expect(mockGet).toHaveBeenCalledTimes(1);
    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('materia_id=7');
    expect(url).toContain('per_page=100');
    expect(result.items.map((r) => r.id)).toEqual([1, 2]);
    expect(result.total).toBe(2);
  });

  it('recorre todas las páginas cuando el total supera per_page', async () => {
    const pagina1 = Array.from({ length: 100 }, (_, i) => item(i + 1));
    const pagina2 = Array.from({ length: 33 }, (_, i) => item(i + 101));

    mockGet
      .mockResolvedValueOnce({ data: { items: pagina1, total: 133, page: 1, per_page: 100 } })
      .mockResolvedValueOnce({ data: { items: pagina2, total: 133, page: 2, per_page: 100 } });

    const result = await rubricasService.getAllPages({ materia_id: 7 });

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(mockGet.mock.calls[1][0]).toContain('page=2');
    expect(result.items).toHaveLength(133);
    expect(result.total).toBe(133);
  });

  it('corta si una página vuelve vacía (total desactualizado) en vez de loopear', async () => {
    const pagina1 = Array.from({ length: 100 }, (_, i) => item(i + 1));

    mockGet
      .mockResolvedValueOnce({ data: { items: pagina1, total: 250, page: 1, per_page: 100 } })
      .mockResolvedValueOnce({ data: { items: [], total: 250, page: 2, per_page: 100 } });

    const result = await rubricasService.getAllPages();

    expect(mockGet).toHaveBeenCalledTimes(2);
    expect(result.items).toHaveLength(100);
  });
});
