import { describe, it, expect } from 'vitest';
import { isAuthEndpoint } from './auth-endpoints';

/**
 * ERR-004: el interceptor global de axios debe distinguir el 401 de un endpoint
 * de autenticación (credenciales inválidas / cambio de contraseña) del 401 de un
 * token expirado. `isAuthEndpoint` es el predicado puro que toma esa decisión.
 */
describe('isAuthEndpoint', () => {
  it('clasifica /auth/login como endpoint de auth', () => {
    expect(isAuthEndpoint('/auth/login')).toBe(true);
  });

  it('clasifica /auth/change-password como endpoint de auth', () => {
    expect(isAuthEndpoint('/auth/change-password')).toBe(true);
  });

  it('no clasifica un endpoint de negocio como auth', () => {
    expect(isAuthEndpoint('/entregas')).toBe(false);
  });

  it('devuelve false para undefined (no hay URL en la config)', () => {
    expect(isAuthEndpoint(undefined)).toBe(false);
  });

  // TRIANGULATE: la URL puede llevar query params o ser una ruta /auth distinta.
  it('reconoce la ruta de auth aunque lleve query params', () => {
    expect(isAuthEndpoint('/auth/login?next=/dashboard')).toBe(true);
  });

  it('no clasifica otras rutas /auth cuyo 401 SÍ es sesión expirada', () => {
    expect(isAuthEndpoint('/auth/me')).toBe(false);
  });
});
