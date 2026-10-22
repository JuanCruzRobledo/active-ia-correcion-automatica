import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { PerfilPage } from './PerfilPage';
import * as perfilService from '../services/perfil-service';
import type { UserProfile } from '../types';

vi.mock('react-hot-toast', () => ({
  default: { success: vi.fn(), error: vi.fn() },
}));
vi.mock('../services/perfil-service');
vi.mock('../../auth/services/auth-service', () => ({
  changePassword: vi.fn(),
}));

const baseProfile: UserProfile = {
  id: 1,
  username: 'tutor1',
  nombre: 'Tutor Uno',
  email: null,
  rol: 'TUTOR',
  primer_login: false,
  gemini_api_key_valid: false,
  gemini_api_key_last_4: null,
  gemini_api_key_paga: false,
  correction_provider: 'gemini',
  openrouter_api_key_valid: false,
  openrouter_api_key_last_4: null,
  moodle_username: null,
  moodle_host: 'https://moodle.tupad.edu.ar',
  moodle_configured: false,
  activo: true,
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-01-01T00:00:00Z',
  last_login: null,
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return render(<PerfilPage />, { wrapper });
}

describe('PerfilPage — modelo OpenRouter', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(perfilService.updateCorrectionProvider).mockReset(); });

  it('oculta el modelo para Gemini Studio', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue(baseProfile);
    renderPage();
    await screen.findByText('Tutor Uno');
    expect(screen.queryByLabelText('Modelo de OpenRouter')).not.toBeInTheDocument();
  });

  it('muestra el modelo predeterminado debajo de la API key', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue({ ...baseProfile, correction_provider: 'openrouter' });
    renderPage();
    const field = await screen.findByLabelText('Modelo de OpenRouter');
    expect(field).toHaveValue('google/gemini-3.8-flash');
    expect(screen.getByText('API Key de OpenRouter (beta)').compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(field).toHaveAccessibleDescription(/copiá el identificador/i);
  });

  it('guarda un modelo personalizado sin volver a ingresar la API key y lo recupera al recargar', async () => {
    let profile = { ...baseProfile, correction_provider: 'openrouter' as const, openrouter_model: 'google/gemini-3.8-flash' };
    vi.mocked(perfilService.getProfile).mockImplementation(async () => profile);
    vi.mocked(perfilService.updateCorrectionProvider).mockImplementation(async (provider, model) => {
      profile = { ...profile, openrouter_model: model ?? profile.openrouter_model };
      return { message: 'Guardado', correction_provider: provider, openrouter_model: profile.openrouter_model };
    });
    const page = renderPage();
    fireEvent.change(await screen.findByLabelText('Modelo de OpenRouter'), { target: { value: ' anthropic/claude-sonnet-5.5 ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar modelo' }));
    await waitFor(() => expect(perfilService.updateCorrectionProvider).toHaveBeenCalledWith('openrouter', 'anthropic/claude-sonnet-5.5'));
    expect(perfilService.updateApiKey).not.toHaveBeenCalled();
    await waitFor(() => expect(screen.getByLabelText('Modelo de OpenRouter')).toHaveValue('anthropic/claude-sonnet-5.5'));
    page.unmount();
    renderPage();
    expect(await screen.findByLabelText('Modelo de OpenRouter')).toHaveValue('anthropic/claude-sonnet-5.5');
  });

  it('permite volver al modelo predeterminado dejando el campo vacío', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue({ ...baseProfile, correction_provider: 'openrouter', openrouter_model: 'anthropic/claude-sonnet-5.5' });
    vi.mocked(perfilService.updateCorrectionProvider).mockResolvedValue({ message: 'Guardado', correction_provider: 'openrouter', openrouter_model: 'google/gemini-3.8-flash' });
    renderPage();
    fireEvent.change(await screen.findByLabelText('Modelo de OpenRouter'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar modelo' }));
    await waitFor(() => expect(perfilService.updateCorrectionProvider).toHaveBeenCalledWith('openrouter', 'google/gemini-3.8-flash'));
  });

  it('bloquea el formulario durante el guardado y conserva la edición ante un error', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue({ ...baseProfile, correction_provider: 'openrouter' });
    let rejectSave!: (error: Error) => void;
    vi.mocked(perfilService.updateCorrectionProvider).mockImplementation(() => new Promise((_resolve, reject) => { rejectSave = reject; }));
    renderPage();
    const field = await screen.findByLabelText('Modelo de OpenRouter');
    fireEvent.change(field, { target: { value: 'modelo-invalido' } });
    fireEvent.click(screen.getByRole('button', { name: 'Guardar modelo' }));
    await waitFor(() => expect(field).toBeDisabled());
    expect(screen.getByRole('button', { name: /guardando/i })).toBeDisabled();
    rejectSave(new Error('Usá el formato proveedor/modelo.'));
    expect(await screen.findByRole('alert')).toHaveTextContent('Usá el formato proveedor/modelo.');
    expect(field).toHaveValue('modelo-invalido');
    expect(field).toBeEnabled();
  });
});
