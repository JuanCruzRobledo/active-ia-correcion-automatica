import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@/shared/services/api-client', () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));

import { apiClient } from '@/shared/services/api-client';
import { universidadesService } from './universidades-service';

const mockGet = apiClient.get as unknown as ReturnType<typeof vi.fn>;
const mockPost = apiClient.post as unknown as ReturnType<typeof vi.fn>;
const mockPut = apiClient.put as unknown as ReturnType<typeof vi.fn>;
const mockDelete = apiClient.delete as unknown as ReturnType<typeof vi.fn>;

describe('universidadesService', () => {
  beforeEach(() => vi.clearAllMocks());

  it('getMias() llama a GET /universidades/mias', async () => {
    const mias = [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }];
    mockGet.mockResolvedValueOnce({ data: mias });

    await expect(universidadesService.getMias()).resolves.toEqual(mias);
    expect(mockGet).toHaveBeenCalledWith('/universidades/mias');
  });

  it('getAll() llama a GET /universidades con los filtros como query params', async () => {
    const list = { items: [], total: 0, page: 1, per_page: 20 };
    mockGet.mockResolvedValueOnce({ data: list });

    await universidadesService.getAll({ includeInactive: true, search: 'TUP' });

    const [url] = mockGet.mock.calls[0];
    expect(url).toContain('/universidades');
    expect(url).toContain('include_inactive=true');
    expect(url).toContain('search=TUP');
  });

  it('create() llama a POST /universidades', async () => {
    const created = { id: 5, nombre: 'Nueva', moodle_host: null, activa: true, created_at: '', updated_at: '' };
    mockPost.mockResolvedValueOnce({ data: created });

    await expect(universidadesService.create({ nombre: 'Nueva' })).resolves.toEqual(created);
    expect(mockPost).toHaveBeenCalledWith('/universidades', { nombre: 'Nueva' });
  });

  it('update() llama a PUT /universidades/{id}', async () => {
    const updated = { id: 1, nombre: 'X', moodle_host: null, activa: true, created_at: '', updated_at: '' };
    mockPut.mockResolvedValueOnce({ data: updated });

    await universidadesService.update(1, { nombre: 'X' });
    expect(mockPut).toHaveBeenCalledWith('/universidades/1', { nombre: 'X' });
  });

  it('remove() llama a DELETE /universidades/{id}', async () => {
    mockDelete.mockResolvedValueOnce({ data: undefined });

    await universidadesService.remove(1);
    expect(mockDelete).toHaveBeenCalledWith('/universidades/1');
  });
});
