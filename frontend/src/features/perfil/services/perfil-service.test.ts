import { beforeEach, describe, expect, it, vi } from 'vitest';
import { apiClient } from '@/shared/services/api-client';
import { updateCorrectionProvider } from './perfil-service';

vi.mock('@/shared/services/api-client', () => ({ apiClient: { patch: vi.fn() } }));

describe('preferencia de modelo de corrección', () => {
  beforeEach(() => vi.resetAllMocks());

  it('envía el modelo personalizado por el endpoint de preferencias sin enviar una key', async () => {
    const response = { message: 'Guardado', correction_provider: 'openrouter', openrouter_model: 'anthropic/claude-sonnet-5.5' };
    vi.mocked(apiClient.patch).mockResolvedValue({ data: response });
    await expect(updateCorrectionProvider('openrouter', response.openrouter_model)).resolves.toEqual(response);
    expect(apiClient.patch).toHaveBeenCalledWith('/perfil/correction-provider', { provider: 'openrouter', openrouter_model: response.openrouter_model });
  });

  it('no sobrescribe el modelo guardado cuando sólo se cambia el proveedor', async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ data: {} });
    await updateCorrectionProvider('gemini');
    expect(apiClient.patch).toHaveBeenCalledWith('/perfil/correction-provider', { provider: 'gemini' });
  });
});
