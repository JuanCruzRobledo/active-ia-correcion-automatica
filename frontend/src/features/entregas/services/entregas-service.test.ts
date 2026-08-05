import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/shared/services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '@/shared/services/api-client';
import { entregasService } from './entregas-service';

const mockGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;

const filtrosBase = { comision_id: 1, rubrica_id: 2 };

const respuestaVacia = {
  data: { items: [], total: 0, page: 1, per_page: 20 },
};

describe('entregasService.restore', () => {
  beforeEach(() => vi.clearAllMocks());

  it('llama al endpoint de restore de esa entrega', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 22279 } });

    await entregasService.restore(22279);

    expect(mockPost).toHaveBeenCalledTimes(1);
    expect(mockPost.mock.calls[0][0]).toBe('/entregas/22279/restore');
  });

  it('devuelve la entrega restaurada', async () => {
    mockPost.mockResolvedValueOnce({ data: { id: 7, alumno_nombre: 'MANUEL GALARZA' } });

    const restaurada = await entregasService.restore(7);

    expect(restaurada.id).toBe(7);
  });
});

describe('entregasService.getAll — filtros de papelera', () => {
  beforeEach(() => vi.clearAllMocks());

  const urlDeLaLlamada = () => String(mockGet.mock.calls[0][0]);

  it('manda solo_eliminadas cuando se pide la papelera', async () => {
    mockGet.mockResolvedValueOnce(respuestaVacia);

    await entregasService.getAll({ ...filtrosBase, solo_eliminadas: true });

    expect(urlDeLaLlamada()).toContain('solo_eliminadas=true');
  });

  it('manda incluir_eliminadas cuando se piden vivas y borradas juntas', async () => {
    mockGet.mockResolvedValueOnce(respuestaVacia);

    await entregasService.getAll({ ...filtrosBase, incluir_eliminadas: true });

    expect(urlDeLaLlamada()).toContain('incluir_eliminadas=true');
  });

  it('no manda ningún filtro de papelera en el listado normal', async () => {
    mockGet.mockResolvedValueOnce(respuestaVacia);

    await entregasService.getAll(filtrosBase);

    const url = urlDeLaLlamada();
    expect(url).not.toContain('eliminadas');
  });
});
