/**
 * Contexto crudo de tenant (D1) — separado de `TenantProvider.tsx` porque
 * `react-refresh/only-export-components` no permite que un archivo exporte a
 * la vez un componente y otros valores (rompe el Fast Refresh). Este archivo
 * no exporta ningún componente, así que puede exportar el Context + su tipo
 * sin problema; `TenantProvider.tsx` y `useTenant.ts` lo consumen.
 */
import { createContext } from 'react';
import type { Rol } from '@/shared/types';

export interface TenantContextValue {
  /** Universidad activa de la sesión vigente. `null` sin universidad elegida. */
  universidadActivaId: number | null;
  /** Rol del usuario en la universidad activa. `null` sin universidad elegida. */
  rol: Rol | null;
  /** `true` si el usuario es admin global (bypass multi-tenant). */
  esSuperadmin: boolean;
  /**
   * Cambia la universidad activa. `null` = modo global (sólo superadmin, D6).
   * Ante error, NO limpia la caché y deja la sesión anterior intacta — el
   * caller decide cómo mostrar el error (propaga la excepción).
   */
  cambiarUniversidad: (universidadId: number | null) => Promise<void>;
}

export const TenantContext = createContext<TenantContextValue | undefined>(undefined);
