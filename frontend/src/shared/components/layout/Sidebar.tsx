import { NavLink } from 'react-router-dom';
import { User, LogOut } from 'lucide-react';
import { cn } from '@/shared/utils';
import { useAuth, useLogout } from '@/features/auth/hooks';
import { useTenant } from '@/shared/context/useTenant';
import { ThemeToggle } from './ThemeToggle';
import { UniversidadSelector } from './UniversidadSelector';
import { navItemsForRole } from './navConfig';

export const Sidebar = () => {
  const { user } = useAuth();
  const { rol, esSuperadmin } = useTenant();
  const logoutMutation = useLogout();

  // D2: el rol es de la membresía activa (useTenant), no del usuario global.
  const userRole = rol || 'admin';
  const userName = user?.nombre || 'Usuario';

  const filteredNavItems = navItemsForRole({ rol, esSuperadmin });

  return (
    // h-screen + flex-col: la barra ocupa el alto exacto del viewport. El <nav> es el
    // único que crece (min-h-0 + overflow-y-auto), así nunca empuja al body ni crea el
    // doble scroll. Compactado (py-2, gaps chicos) para que entre sin scroll en pantallas
    // normales; si la pantalla es muy baja, scrollea SOLO el nav, no toda la página.
    <aside className="hidden h-screen lg:flex lg:w-64 lg:flex-col bg-sidebar border-r border-sidebar-border">
      {/* Logo */}
      <div className="flex shrink-0 items-center gap-2 border-b border-sidebar-border p-4">
        <img src="/active-ia-logo.svg" alt="Active-IA Logo" className="h-8 w-8" />
        <span className="text-base font-semibold text-sidebar-foreground">Active-IA</span>
      </div>

      {/* Navigation */}
      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-3 py-3">
        {filteredNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent'
              )
            }
          >
            <item.icon className="h-[18px] w-[18px] shrink-0" />
            <span className="truncate">{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* Selector de universidad (D1/D5) */}
      <div className="shrink-0 border-t border-sidebar-border p-3">
        <UniversidadSelector />
      </div>

      {/* User footer */}
      <div className="shrink-0 border-t border-sidebar-border p-3">
        <div className="space-y-0.5">
          <NavLink
            to="/perfil"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                isActive ? 'bg-sidebar-accent' : 'text-sidebar-foreground hover:bg-sidebar-accent'
              )
            }
          >
            <User className="h-[18px] w-[18px] shrink-0" />
            <div className="flex-1 truncate">
              <p className="truncate font-medium">{userName}</p>
              <p className="truncate text-xs text-muted-foreground">
                {userRole.charAt(0) + userRole.slice(1).toLowerCase()}
              </p>
            </div>
          </NavLink>

          <ThemeToggle />

          <button
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            <LogOut className="h-[18px] w-[18px] shrink-0" />
            <span>{logoutMutation.isPending ? 'Cerrando...' : 'Cerrar sesión'}</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
