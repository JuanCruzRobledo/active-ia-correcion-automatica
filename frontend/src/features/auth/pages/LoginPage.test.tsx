import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { AxiosError, AxiosHeaders } from 'axios';
import type { AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { LoginPage } from './LoginPage';
import { login, seleccionarUniversidad } from '../services/auth-service';
import type { UserInfo } from '@/shared/types';

const navigateMock = vi.fn();

vi.mock('react-hot-toast', () => ({
  default: { error: vi.fn(), success: vi.fn() },
}));
vi.mock('../services/auth-service');
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal<typeof import('react-router-dom')>();
  return { ...actual, useNavigate: () => navigateMock };
});

function makeAxiosError(status: number, detail: string): AxiosError<{ detail?: string }> {
  const config: InternalAxiosRequestConfig = { url: '/auth/login', headers: new AxiosHeaders() };
  const response: AxiosResponse<{ detail?: string }> = {
    status,
    statusText: '',
    data: { detail },
    headers: {},
    config,
  };
  return new AxiosError<{ detail?: string }>(
    `Request failed with status code ${status}`,
    'ERR_BAD_REQUEST',
    config,
    undefined,
    response
  );
}

function makeUser(over: Partial<UserInfo> = {}): UserInfo {
  return {
    id: 1,
    username: 'multiuni',
    nombre: 'Multi Uni',
    rol: null,
    primer_login: false,
    gemini_api_key_valid: false,
    universidad_activa_id: null,
    es_superadmin: false,
    ...over,
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
  return render(<LoginPage />, { wrapper });
}

async function submitLogin(username = 'multiuni', password = 'x') {
  fireEvent.change(screen.getByLabelText('Usuario'), { target: { value: username } });
  fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: password } });
  fireEvent.click(screen.getByRole('button', { name: /iniciar sesión/i }));
}

describe('LoginPage — segundo paso de selección de universidad', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('con requiere_seleccion: muestra las universidades disponibles, cada una con su rol', async () => {
    vi.mocked(login).mockResolvedValue({
      requiere_seleccion: true,
      universidades: [
        { id: 1, nombre: 'TUPaD', rol: 'TUTOR' },
        { id: 2, nombre: 'Otra Uni', rol: 'COORDINADOR' },
      ],
      token_transicion: 'tok-transicion',
    });

    renderPage();
    await submitLogin();

    expect(await screen.findByText('TUPaD')).toBeInTheDocument();
    expect(screen.getByText('Otra Uni')).toBeInTheDocument();
    expect(screen.getByText(/TUTOR/i)).toBeInTheDocument();
    expect(screen.getByText(/COORDINADOR/i)).toBeInTheDocument();
  });

  it('al elegir una universidad, llama a select-universidad con el token de transición', async () => {
    vi.mocked(login).mockResolvedValue({
      requiere_seleccion: true,
      universidades: [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }],
      token_transicion: 'tok-transicion',
    });
    vi.mocked(seleccionarUniversidad).mockResolvedValue({
      access_token: 'JWT-FINAL',
      token_type: 'bearer',
      user: makeUser({ universidad_activa_id: 1, rol: 'TUTOR' }),
    });

    renderPage();
    await submitLogin();

    const opcion = await screen.findByText('TUPaD');
    fireEvent.click(opcion);

    await waitFor(() =>
      expect(seleccionarUniversidad).toHaveBeenCalledWith('tok-transicion', 1)
    );
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/dashboard', { replace: true }));
  });

  it('volver atrás sin elegir: descarta el token_transicion y vuelve al formulario', async () => {
    vi.mocked(login).mockResolvedValue({
      requiere_seleccion: true,
      universidades: [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }],
      token_transicion: 'tok-transicion',
    });

    renderPage();
    await submitLogin();

    await screen.findByText('TUPaD');
    fireEvent.click(screen.getByRole('button', { name: /volver/i }));

    expect(await screen.findByLabelText('Usuario')).toBeInTheDocument();
    expect(seleccionarUniversidad).not.toHaveBeenCalled();
  });

  it('token de transición vencido (401 al elegir): vuelve al formulario con mensaje de reintentar', async () => {
    vi.mocked(login).mockResolvedValue({
      requiere_seleccion: true,
      universidades: [{ id: 1, nombre: 'TUPaD', rol: 'TUTOR' }],
      token_transicion: 'tok-transicion',
    });
    vi.mocked(seleccionarUniversidad).mockRejectedValue(
      makeAxiosError(401, 'Token de selección vencido')
    );

    renderPage();
    await submitLogin();

    fireEvent.click(await screen.findByText('TUPaD'));

    expect(await screen.findByLabelText('Usuario')).toBeInTheDocument();
    expect(await screen.findByText(/volvé a intentar/i)).toBeInTheDocument();
  });
});

describe('LoginPage — usuario sin universidad asignada (403)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra el mensaje del backend, distinguible de un error de credenciales', async () => {
    vi.mocked(login).mockRejectedValue(
      makeAxiosError(403, 'Usuario sin universidad asignada. Contactá a un administrador.')
    );

    renderPage();
    await submitLogin();

    expect(
      await screen.findByText('Usuario sin universidad asignada. Contactá a un administrador.')
    ).toBeInTheDocument();
    expect(screen.queryByText(/verifica tus credenciales/i)).not.toBeInTheDocument();
  });
});
