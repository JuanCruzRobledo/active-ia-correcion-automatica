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
  FileSpreadsheet,
  Building2,
} from 'lucide-react';

export interface NavItem {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  roles?: string[];
  /**
   * Marca el item como "primario": entra en la bottom tab bar mobile (máx 4 slots
   * por rol, el 5º es siempre "Más"). El resto cae al overflow / bottom-sheet "Más".
   * El Sidebar desktop ignora este flag y muestra todos los items.
   */
  primary?: boolean;
}

export const navItems: NavItem[] = [
  { to: '/dashboard', icon: Home, label: 'Dashboard', primary: true },
  // roles: [] (no `undefined`) = sólo superadmin (D3/puedeVer): ningún rol de
  // membresía satisface un array vacío, y el bypass de superadmin sigue aplicando.
  { to: '/universidades', icon: Building2, label: 'Universidades', roles: [] },
  { to: '/usuarios', icon: Users, label: 'Usuarios', roles: ['ADMIN'] },
  { to: '/materias', icon: BookOpen, label: 'Materias', roles: ['ADMIN', 'COORDINADOR'], primary: true },
  { to: '/cohortes', icon: GraduationCap, label: 'Cohortes', roles: ['ADMIN'] },
  { to: '/snapshots', icon: CalendarClock, label: 'Snapshots', roles: ['ADMIN'] },
  { to: '/tutores-nexo', icon: Mail, label: 'Tutores Nexo', roles: ['ADMIN'] },
  { to: '/notificaciones', icon: BellRing, label: 'Notificaciones', roles: ['ADMIN'] },
  {
    to: '/comisiones',
    icon: FolderOpen,
    label: 'Comisiones',
    roles: ['ADMIN', 'COORDINADOR', 'TUTOR'],
    primary: true,
  },
  { to: '/rubricas', icon: FileText, label: 'Rúbricas', roles: ['ADMIN', 'COORDINADOR'] },
  {
    to: '/cierre-cursada',
    icon: FileSpreadsheet,
    label: 'Cierre de cursada',
    roles: ['ADMIN', 'COORDINADOR'],
  },
  {
    to: '/entregas',
    icon: CheckSquare,
    label: 'Entregas',
    roles: ['TUTOR', 'ADMIN', 'COORDINADOR'],
    primary: true,
  },
  { to: '/pendientes', icon: Clock, label: 'Pendientes', roles: ['TUTOR', 'ADMIN'], primary: true },
  { to: '/por-entregar', icon: Send, label: 'Por entregar', roles: ['TUTOR', 'ADMIN'] },
  { to: '/avance', icon: PieChart, label: 'Avance', roles: ['GESTOR', 'ADMIN'], primary: true },
  { to: '/gestion', icon: BarChart3, label: 'Gestión', roles: ['GESTOR', 'ADMIN'], primary: true },
];

/** Rol + flag de superadmin de la universidad activa (D3: fuente para el gating). */
export interface RolContext {
  rol: string | null;
  esSuperadmin: boolean;
}

/**
 * Regla única de visibilidad de un item de menú (D3).
 *
 * Un superadmin ve TODO, incluso con `rol = null` (todavía no eligió
 * universidad / modo global). El resto sigue la regla de siempre: sin
 * `roles` declarados es visible para cualquiera; con `roles`, sólo si el rol
 * de la universidad activa está en la lista.
 */
export const puedeVer = (item: NavItem, ctx: RolContext): boolean =>
  ctx.esSuperadmin || !item.roles || (ctx.rol != null && item.roles.includes(ctx.rol));

/** Filtra los items del menú según el rol/superadmin (fuente para el Sidebar desktop). */
export const navItemsForRole = (ctx: RolContext): NavItem[] =>
  navItems.filter((item) => puedeVer(item, ctx));

/** Cantidad máxima de items primarios en la bottom bar antes del slot "Más". */
export const MAX_PRIMARY_NAV = 4;

/**
 * Items primarios para la bottom tab bar mobile: máx {@link MAX_PRIMARY_NAV},
 * marcados con `primary` y visibles para el rol. Si algún rol tuviera menos de 4
 * items primarios definidos, se completa con los primeros items disponibles para
 * mantener slots útiles; si tuviera más, se recorta a los primeros 4 (en orden de
 * `navItems`). El reparto por rol queda:
 *   ADMIN/COORDINADOR → Dashboard · Materias · Comisiones · (Entregas)
 *   TUTOR             → Dashboard · Comisiones · Entregas · Pendientes
 *   GESTOR            → Dashboard · Avance · Gestión
 */
export const primaryNavForRole = (ctx: RolContext): NavItem[] => {
  const visibles = navItemsForRole(ctx);
  const primarios = visibles.filter((item) => item.primary);
  // Completar con no-primarios si por algún rol quedan menos de 4 slots útiles.
  const base = primarios.length >= MAX_PRIMARY_NAV
    ? primarios
    : [...primarios, ...visibles.filter((item) => !item.primary)];
  return base.slice(0, MAX_PRIMARY_NAV);
};

/**
 * Items de overflow para el bottom-sheet "Más": todos los items visibles para el
 * rol que NO entraron en la bottom bar (ver {@link primaryNavForRole}).
 */
export const overflowNavForRole = (ctx: RolContext): NavItem[] => {
  const primarios = new Set(primaryNavForRole(ctx).map((item) => item.to));
  return navItemsForRole(ctx).filter((item) => !primarios.has(item.to));
};
