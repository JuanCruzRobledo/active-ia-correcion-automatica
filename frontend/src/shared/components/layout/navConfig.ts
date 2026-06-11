// Configuración compartida del menú de navegación (Sidebar + MobileHeader).
import {
  Home,
  Users,
  BookOpen,
  Clock,
  FolderOpen,
  FileText,
  CheckSquare,
  Send,
  BarChart3,
  GraduationCap,
  CalendarClock,
  PieChart,
  Mail,
  BellRing,
} from 'lucide-react';

export interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  roles?: string[];
}

export const navItems: NavItem[] = [
  { to: '/dashboard', icon: Home, label: 'Dashboard' },
  { to: '/usuarios', icon: Users, label: 'Usuarios', roles: ['ADMIN'] },
  { to: '/materias', icon: BookOpen, label: 'Materias', roles: ['ADMIN', 'COORDINADOR'] },
  { to: '/cohortes', icon: GraduationCap, label: 'Cohortes', roles: ['ADMIN'] },
  { to: '/snapshots', icon: CalendarClock, label: 'Snapshots', roles: ['ADMIN'] },
  { to: '/tutores-nexo', icon: Mail, label: 'Tutores Nexo', roles: ['ADMIN'] },
  { to: '/notificaciones', icon: BellRing, label: 'Notificaciones', roles: ['ADMIN'] },
  {
    to: '/comisiones',
    icon: FolderOpen,
    label: 'Comisiones',
    roles: ['ADMIN', 'COORDINADOR', 'TUTOR'],
  },
  { to: '/rubricas', icon: FileText, label: 'Rúbricas', roles: ['ADMIN', 'COORDINADOR'] },
  { to: '/entregas', icon: CheckSquare, label: 'Entregas', roles: ['TUTOR', 'ADMIN', 'COORDINADOR'] },
  { to: '/pendientes', icon: Clock, label: 'Pendientes', roles: ['TUTOR', 'ADMIN'] },
  { to: '/por-entregar', icon: Send, label: 'Por entregar', roles: ['TUTOR', 'ADMIN'] },
  { to: '/avance', icon: PieChart, label: 'Avance', roles: ['GESTOR', 'ADMIN'] },
  { to: '/gestion', icon: BarChart3, label: 'Gestión', roles: ['GESTOR', 'ADMIN'] },
];

/** Filtra los items del menú según el rol del usuario. */
export const navItemsForRole = (rol: string): NavItem[] =>
  navItems.filter((item) => !item.roles || item.roles.includes(rol));
