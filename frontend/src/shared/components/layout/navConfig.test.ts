import { describe, it, expect } from 'vitest';
import { puedeVer, navItemsForRole, navItems } from './navConfig';
import type { NavItem } from './navConfig';

const conRoles: NavItem = { to: '/usuarios', icon: navItems[0].icon, label: 'Usuarios', roles: ['ADMIN'] };
const sinRoles: NavItem = { to: '/dashboard', icon: navItems[0].icon, label: 'Dashboard' };

describe('puedeVer (D3: gating de navegación con bypass de superadmin)', () => {
  it('superadmin con rol = null ve un item que declara roles', () => {
    expect(puedeVer(conRoles, { rol: null, esSuperadmin: true })).toBe(true);
  });

  it('no-superadmin con rol = null NO ve un item que declara roles', () => {
    expect(puedeVer(conRoles, { rol: null, esSuperadmin: false })).toBe(false);
  });

  it('no-superadmin con rol = null SÍ ve un item sin roles declarados', () => {
    expect(puedeVer(sinRoles, { rol: null, esSuperadmin: false })).toBe(true);
  });

  it('usuario normal ve un item cuyo rol está en la lista', () => {
    expect(puedeVer(conRoles, { rol: 'ADMIN', esSuperadmin: false })).toBe(true);
  });

  it('usuario normal NO ve un item cuyo rol no está en la lista', () => {
    expect(puedeVer(conRoles, { rol: 'TUTOR', esSuperadmin: false })).toBe(false);
  });

  it('item con roles=[] (sólo-superadmin): esSuperadmin lo ve, un ADMIN normal NO', () => {
    const soloSuperadmin: NavItem = { to: '/universidades', icon: navItems[0].icon, label: 'Universidades', roles: [] };
    expect(puedeVer(soloSuperadmin, { rol: null, esSuperadmin: true })).toBe(true);
    expect(puedeVer(soloSuperadmin, { rol: 'ADMIN', esSuperadmin: false })).toBe(false);
  });
});

describe('navItemsForRole', () => {
  it('superadmin ve TODOS los items del menú, no sólo los que no declaran roles', () => {
    const visibles = navItemsForRole({ rol: null, esSuperadmin: true });
    expect(visibles).toHaveLength(navItems.length);
  });

  it('no-superadmin con rol = null ve únicamente los items sin roles', () => {
    const visibles = navItemsForRole({ rol: null, esSuperadmin: false });
    expect(visibles.every((item) => !item.roles)).toBe(true);
    expect(visibles.length).toBeGreaterThan(0);
    expect(visibles.length).toBeLessThan(navItems.length);
  });
});
