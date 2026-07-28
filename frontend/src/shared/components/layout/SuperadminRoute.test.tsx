import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { SuperadminRoute } from './SuperadminRoute';
import { useTenant } from '@/shared/context/useTenant';

vi.mock('@/shared/context/useTenant', () => ({ useTenant: vi.fn() }));

function renderWithRoute(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/universidades"
          element={
            <SuperadminRoute>
              <div>Panel de universidades</div>
            </SuperadminRoute>
          }
        />
        <Route path="/dashboard" element={<div>Dashboard</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe('SuperadminRoute (4.6: guard de ruta del ABM)', () => {
  beforeEach(() => vi.clearAllMocks());

  it('superadmin: renderiza el contenido protegido', () => {
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: null,
      rol: null,
      esSuperadmin: true,
      cambiarUniversidad: vi.fn(),
    });

    renderWithRoute('/universidades');

    expect(screen.getByText('Panel de universidades')).toBeInTheDocument();
  });

  it('no-superadmin: NO puede entrar a la ruta, se redirige a /dashboard', () => {
    vi.mocked(useTenant).mockReturnValue({
      universidadActivaId: 1,
      rol: 'ADMIN',
      esSuperadmin: false,
      cambiarUniversidad: vi.fn(),
    });

    renderWithRoute('/universidades');

    expect(screen.queryByText('Panel de universidades')).not.toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
