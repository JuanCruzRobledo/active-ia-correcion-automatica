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

describe('PerfilPage — credenciales Moodle por universidad (D: campus read-only)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('el formulario NO pide el campus como campo editable; lo muestra de sólo lectura', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue(baseProfile);

    renderPage();
    await screen.findByText('Tutor Uno');

    expect(screen.queryByLabelText(/host moodle/i)).not.toBeInTheDocument();
    expect(screen.getByText('https://moodle.tupad.edu.ar')).toBeInTheDocument();
  });

  it('el guardado envía sólo usuario y contraseña, sin moodle_host', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue(baseProfile);
    vi.mocked(perfilService.updateMoodleCredentials).mockResolvedValue({
      moodle_username: 'nuevo_user',
      moodle_host: 'https://moodle.tupad.edu.ar',
      configured: true,
    });

    renderPage();
    await screen.findByText('Tutor Uno');

    fireEvent.change(screen.getByLabelText(/usuario moodle/i), {
      target: { value: 'nuevo_user' },
    });
    fireEvent.change(screen.getByLabelText(/contraseña moodle/i), {
      target: { value: 'secreto123' },
    });
    fireEvent.click(screen.getByRole('button', { name: /guardar credenciales/i }));

    await waitFor(() => expect(perfilService.updateMoodleCredentials).toHaveBeenCalled());
    expect(vi.mocked(perfilService.updateMoodleCredentials).mock.calls[0][0]).toEqual({
      moodle_username: 'nuevo_user',
      moodle_password: 'secreto123',
    });
  });

  it('universidad activa sin campus configurado: lo indica explícitamente con una advertencia', async () => {
    vi.mocked(perfilService.getProfile).mockResolvedValue({
      ...baseProfile,
      moodle_host: null,
    });

    renderPage();
    await screen.findByText('Tutor Uno');

    expect(await screen.findByText(/no tiene un campus de moodle configurado/i)).toBeInTheDocument();
  });
});
