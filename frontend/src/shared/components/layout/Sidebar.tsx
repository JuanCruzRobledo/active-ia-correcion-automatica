import { NavLink } from 'react-router-dom';
import {
  Home,
  Users,
  BookOpen,
  FolderOpen,
  FileText,
  CheckSquare,
  User,
  LogOut,
} from 'lucide-react';
import { cn } from '@/shared/utils';
import { useAuth, useLogout } from '@/features/auth/hooks';

interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  roles?: string[];
}

const navItems: NavItem[] = [
  { to: '/dashboard', icon: Home, label: 'Dashboard' },
  { to: '/usuarios', icon: Users, label: 'Usuarios', roles: ['ADMIN'] },
  { to: '/materias', icon: BookOpen, label: 'Materias', roles: ['ADMIN'] },
  {
    to: '/comisiones',
    icon: FolderOpen,
    label: 'Comisiones',
    roles: ['ADMIN', 'COORDINADOR'],
  },
  {
    to: '/rubricas',
    icon: FileText,
    label: 'Rúbricas',
    roles: ['ADMIN', 'COORDINADOR'],
  },
  { to: '/entregas', icon: CheckSquare, label: 'Entregas', roles: ['TUTOR'] },
];

export const Sidebar = () => {
  const { user } = useAuth();
  const logoutMutation = useLogout();

  // Use user data from auth or fallback to defaults
  const userRole = user?.rol || 'admin';
  const userName = user?.nombre || 'Usuario';

  const filteredNavItems = navItems.filter(
    (item) => !item.roles || item.roles.includes(userRole)
  );

  return (
    <aside className="hidden lg:flex lg:w-64 lg:flex-col bg-sidebar border-r border-sidebar-border">
      {/* Logo */}
      <div className="flex items-center gap-2 border-b border-sidebar-border p-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent">
          <CheckSquare className="h-6 w-6 text-accent-foreground" />
        </div>
        <span className="text-lg font-semibold text-sidebar-foreground">
          Active-IA
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-4">
        {filteredNavItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      {/* User footer */}
      <div className="border-t border-sidebar-border p-4">
        <div className="space-y-1">
          <NavLink
            to="/perfil"
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-4 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-sidebar-accent'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent'
              )
            }
          >
            <User className="h-5 w-5" />
            <div className="flex-1 truncate">
              <p className="truncate font-medium">{userName}</p>
              <p className="truncate text-xs text-muted-foreground">
                {userRole.charAt(0) + userRole.slice(1).toLowerCase()}
              </p>
            </div>
          </NavLink>

          <button
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
            className="flex w-full items-center gap-3 rounded-lg px-4 py-2 text-sm text-sidebar-foreground transition-colors hover:bg-sidebar-accent disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <LogOut className="h-5 w-5" />
            <span>{logoutMutation.isPending ? 'Cerrando...' : 'Cerrar sesión'}</span>
          </button>
        </div>
      </div>
    </aside>
  );
};
