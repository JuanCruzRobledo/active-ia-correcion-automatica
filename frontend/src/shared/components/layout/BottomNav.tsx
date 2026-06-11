import { useState } from 'react';
import { Menu, User, LogOut } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/shared/utils';
import { useAuth, useLogout } from '@/features/auth/hooks';
import { ThemeToggle } from './ThemeToggle';
import { Sheet } from './Sheet';
import { primaryNavForRole, overflowNavForRole } from './navConfig';
import type { NavItem } from './navConfig';

interface BottomNavProps {
  className?: string;
}

// Clases compartidas por cada slot de la barra (NavLink primario y botón "Más").
const slotClass =
  'relative flex min-h-14 flex-col items-center justify-center gap-0.5 px-1 ' +
  'touch-manipulation select-none transition-colors';

const labelClass = 'max-w-full truncate text-[10px] leading-tight';

/**
 * Bottom tab bar mobile (oculta en desktop con `lg:hidden`).
 *
 * Muestra hasta 4 items primarios del rol + un 5º slot "Más" que abre un
 * bottom-sheet con el overflow de navegación y las acciones de cuenta.
 * Item activo resaltado vía la clase `.active` que inyecta NavLink (React Router).
 */
export const BottomNav = ({ className }: BottomNavProps) => {
  const { user } = useAuth();
  const [moreOpen, setMoreOpen] = useState(false);

  const userRole = user?.rol || 'admin';
  const primary = primaryNavForRole(userRole);
  const overflow = overflowNavForRole(userRole);
  const hasOverflow = overflow.length > 0;

  // Si no hay overflow, todos los slots son items; si lo hay, reservamos el 5º para "Más".
  const primaryToShow = hasOverflow ? primary.slice(0, 4) : primary.slice(0, 5);
  const totalSlots = primaryToShow.length + (hasOverflow ? 1 : 0);

  return (
    <>
      <nav
        aria-label="Navegación principal"
        className={cn(
          'fixed inset-x-0 bottom-0 z-40 grid border-t border-border',
          'bg-background/95 backdrop-blur-md pb-[env(safe-area-inset-bottom)]',
          'lg:hidden',
          className
        )}
        style={{ gridTemplateColumns: `repeat(${totalSlots}, minmax(0, 1fr))` }}
      >
        {primaryToShow.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={cn(
              slotClass,
              'text-muted-foreground [&.active]:text-foreground'
            )}
          >
            {({ isActive }) => (
              <>
                {/* Indicador de activo: barra superior fina. */}
                <span
                  aria-hidden="true"
                  className={cn(
                    'absolute top-0 h-0.5 w-8 rounded-full transition-opacity',
                    isActive ? 'bg-primary opacity-100' : 'opacity-0'
                  )}
                />
                <item.icon className="h-6 w-6" />
                <span className={labelClass}>{item.label}</span>
              </>
            )}
          </NavLink>
        ))}

        {hasOverflow && (
          <button
            type="button"
            onClick={() => setMoreOpen(true)}
            aria-haspopup="dialog"
            aria-expanded={moreOpen}
            className={cn(slotClass, 'text-muted-foreground hover:text-foreground')}
          >
            <Menu className="h-6 w-6" />
            <span className={labelClass}>Más</span>
          </button>
        )}
      </nav>

      <MoreSheet
        open={moreOpen}
        onClose={() => setMoreOpen(false)}
        items={overflow}
        userName={user?.nombre || 'Usuario'}
        userRole={userRole}
      />
    </>
  );
};

interface MoreSheetProps {
  open: boolean;
  onClose: () => void;
  items: NavItem[];
  userName: string;
  userRole: string;
}

/**
 * Bottom-sheet "Más": lista el overflow de navegación + acciones de cuenta
 * (perfil, theme toggle, cerrar sesión). Usa el primitivo {@link Sheet}.
 */
const MoreSheet = ({ open, onClose, items, userName, userRole }: MoreSheetProps) => {
  const logoutMutation = useLogout();
  const roleLabel = userRole.charAt(0) + userRole.slice(1).toLowerCase();

  const handleLogout = () => {
    onClose();
    logoutMutation.mutate();
  };

  return (
    <Sheet open={open} onClose={onClose} title="Más opciones">
      <div className="px-3 pb-3">
        {/* Encabezado con el usuario. */}
        <p className="px-3 py-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          {userName} · {roleLabel}
        </p>

        {/* Overflow de navegación. */}
        {items.length > 0 && (
          <nav className="space-y-0.5">
            {items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onClose}
                className={({ isActive }) =>
                  cn(
                    'flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-medium',
                    'touch-manipulation transition-colors',
                    isActive
                      ? 'bg-accent text-accent-foreground'
                      : 'text-foreground hover:bg-muted'
                  )
                }
              >
                <item.icon className="h-5 w-5 shrink-0" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            ))}
          </nav>
        )}

        {/* Acciones de cuenta. */}
        <div className="mt-2 space-y-0.5 border-t border-border pt-2">
          <NavLink
            to="/perfil"
            onClick={onClose}
            className={({ isActive }) =>
              cn(
                'flex min-h-12 items-center gap-3 rounded-lg px-3 text-sm font-medium',
                'touch-manipulation transition-colors',
                isActive ? 'bg-accent text-accent-foreground' : 'text-foreground hover:bg-muted'
              )
            }
          >
            <User className="h-5 w-5 shrink-0" />
            <span>Perfil</span>
          </NavLink>

          <ThemeToggle className="min-h-12 text-foreground hover:bg-muted" />

          <button
            type="button"
            onClick={handleLogout}
            disabled={logoutMutation.isPending}
            className={cn(
              'flex min-h-12 w-full items-center gap-3 rounded-lg px-3 text-sm',
              'touch-manipulation text-foreground transition-colors hover:bg-muted',
              'disabled:cursor-not-allowed disabled:opacity-50'
            )}
          >
            <LogOut className="h-5 w-5 shrink-0" />
            <span>{logoutMutation.isPending ? 'Cerrando...' : 'Cerrar sesión'}</span>
          </button>
        </div>
      </div>
    </Sheet>
  );
};
