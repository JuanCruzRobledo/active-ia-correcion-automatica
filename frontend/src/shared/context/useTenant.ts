/**
 * useTenant — hook de acceso al contexto de tenant (D1).
 *
 * Separado de `TenantProvider.tsx` (ver `tenant-context.ts`) para que ese
 * archivo sólo exporte el componente `TenantProvider`, requisito de
 * `react-refresh/only-export-components`.
 */
import { useContext } from 'react';
import { TenantContext } from './tenant-context';
import type { TenantContextValue } from './tenant-context';

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext);
  if (!ctx) {
    throw new Error('useTenant debe usarse dentro de <TenantProvider>');
  }
  return ctx;
}
