import { describe, it, expect, vi, beforeEach } from 'vitest';
import type { ReactNode } from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { UsuariosPage } from '../UsuariosPage';
import { usuariosService } from '../../services/usuarios-service';
import type { UsuarioListItem } from '../../types';

// Mockeamos el service (para controlar la lista y espiar el borrado) y el toast.
vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../../services/usuarios-service', () => ({
  usuariosService: {
    getAll: vi.fn(),
    delete: vi.fn(),
    restore: vi.fn(),
  },
}));

const usuarioActivo: UsuarioListItem = {
  id: 7,
  username: 'jperez',
  nombre: 'Juan Pérez',
  rol: 'TUTOR',
  activo: true,
  created_at: '2024-01-01T00:00:00Z',
  last_login: null,
};

const renderPage = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return render(<UsuariosPage />, { wrapper });
};

// Abre el dropdown de acciones de la primera fila (desktop + mobile comparten
// markup, por eso tomamos el primero) y devuelve el diálogo de confirmación
// tras pulsar "Eliminar" en el menú.
const openEliminarDialog = async () => {
  const acciones = await screen.findAllByLabelText('Acciones');
  fireEvent.click(acciones[0]);
  const eliminarItem = await screen.findByText('Eliminar');
  fireEvent.click(eliminarItem);
};

describe('UsuariosPage — flujo confirmar → eliminar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(usuariosService.getAll).mockResolvedValue({
      items: [usuarioActivo],
      total: 1,
      page: 1,
      per_page: 20,
    });
  });

  it('al pulsar "Eliminar" en el dropdown abre el diálogo de confirmación y NO borra todavía', async () => {
    renderPage();
    await screen.findAllByText('Juan Pérez');

    await openEliminarDialog();

    // Aparece el diálogo destructivo de confirmación.
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Eliminar usuario')).toBeInTheDocument();

    // Sin confirmar, el borrado NO se disparó.
    expect(usuariosService.delete).not.toHaveBeenCalled();
  });

  it('al confirmar, borra el usuario correcto, muestra toast de éxito y cierra el diálogo', async () => {
    vi.mocked(usuariosService.delete).mockResolvedValue(undefined);

    renderPage();
    await screen.findAllByText('Juan Pérez');

    await openEliminarDialog();
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Eliminar' }));

    await waitFor(() =>
      expect(usuariosService.delete).toHaveBeenCalledWith(7)
    );
    expect(toast.success).toHaveBeenCalledWith('Usuario eliminado');
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
  });

  it('al cancelar, NO borra y el diálogo desaparece', async () => {
    renderPage();
    await screen.findAllByText('Juan Pérez');

    await openEliminarDialog();
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }));

    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    );
    expect(usuariosService.delete).not.toHaveBeenCalled();
  });
});
