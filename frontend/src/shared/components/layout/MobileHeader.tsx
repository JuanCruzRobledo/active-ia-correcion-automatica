import { useState } from 'react';
import { Menu, X, User, LogOut } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/shared/utils';
import { useAuth, useLogout } from '@/features/auth/hooks';
import { ThemeToggle } from './ThemeToggle';
import { navItemsForRole } from './navConfig';

export const MobileHeader = () => {
  const [isOpen, setIsOpen] = useState(false);
  const { user } = useAuth();
  const logoutMutation = useLogout();

  const userRole = user?.rol || 'admin';
  const userName = user?.nombre || 'Usuario';
  const filteredNavItems = navItemsForRole(userRole);

  const close = () => setIsOpen(false);

  return (
    <header className="lg:hidden sticky top-0 z-50 border-b border-border bg-background">
      <div className="flex h-16 items-center justify-between px-4">
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="rounded-lg p-2 hover:bg-muted"
          aria-label="Toggle menu"
        >
          {isOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
        </button>

        <div className="flex items-center gap-2">
          <img src="/active-ia-logo.svg" alt="Active-IA Logo" className="h-8 w-8" />
          <span className="text-lg font-semibold">Active-IA</span>
        </div>

        <div className="flex items-center gap-1">
          <ThemeToggle variant="icon" />
          <NavLink to="/perfil" className="rounded-full p-2 hover:bg-muted" aria-label="Perfil">
            <User className="h-6 w-6" />
          </NavLink>
        </div>
      </div>

      {/* Mobile menu */}
      {isOpen && (
        <div className="max-h-[calc(100vh-4rem)] overflow-y-auto border-t border-border bg-background p-3">
          <p className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            {userName} · {userRole.charAt(0) + userRole.slice(1).toLowerCase()}
          </p>
          <nav className="space-y-0.5">
            {filteredNavItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={close}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-accent text-accent-foreground'
                      : 'text-foreground hover:bg-muted'
                  )
                }
              >
                <item.icon className="h-5 w-5 shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            ))}
            <button
              onClick={() => {
                close();
                logoutMutation.mutate();
              }}
              disabled={logoutMutation.isPending}
              className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-foreground transition-colors hover:bg-muted disabled:opacity-50"
            >
              <LogOut className="h-5 w-5 shrink-0" />
              <span>Cerrar sesión</span>
            </button>
          </nav>
        </div>
      )}
    </header>
  );
};
