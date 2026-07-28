/**
 * TenantProvider — contexto reactivo de universidad activa (D1).
 *
 * `localStorage` sigue siendo la persistencia de la sesión (durabilidad entre
 * recargas); este Context aporta la reactividad que `localStorage` no tiene
 * por sí solo. El estado se DERIVA de la sesión vigente — no la reemplaza —
 * y se re-sincroniza ante `AUTH_SESSION_EVENT` (persistencia de sesión en la
 * misma pestaña: login, selección o switch de universidad) y `storage`
 * (sincronización entre pestañas).
 *
 * D4 (requisito más crítico del change): `cambiarUniversidad` limpia la
 * TOTALIDAD de la caché de React Query con `queryClient.clear()`, nunca
 * `invalidateQueries()` selectivo — `invalidate` deja servidos los datos
 * viejos mientras revalida, lo que filtraría datos de un tenant a otro.
 * Antes de `clear()` se cancelan las queries en vuelo (`cancelQueries()`):
 * sin esto, una respuesta tardía del tenant anterior que resuelve después
 * del switch puede reescribirse en la caché ya "limpia" del tenant nuevo si
 * el mismo query key sigue montado.
 *
 * El hook `useTenant()` vive en `./useTenant.ts` (y el Context crudo en
 * `./tenant-context.ts`): este archivo sólo exporta el componente
 * `TenantProvider`, requisito de `react-refresh/only-export-components`.
 *
 * Ref: openspec/changes/multi-tenant-frontend-workspace/design.md (D1, D4, D6)
 */
import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import {
  AUTH_SESSION_EVENT,
  getUser,
  switchUniversidad,
} from '@/features/auth/services/auth-service';
import { TenantContext } from './tenant-context';
import type { TenantContextValue } from './tenant-context';

export function TenantProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(() => getUser());

  useEffect(() => {
    const sync = () => setUser(getUser());
    // AUTH_SESSION_EVENT: misma pestaña (localStorage no es reactivo intra-tab).
    // storage: sincronización entre pestañas (evento nativo, no dispara en la
    // pestaña que escribió).
    window.addEventListener(AUTH_SESSION_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(AUTH_SESSION_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  const cambiarUniversidad = async (universidadId: number | null): Promise<void> => {
    // switchUniversidad persiste la sesión nueva y dispara AUTH_SESSION_EVENT
    // (el listener de arriba actualiza `user`). Si falla, no se persiste nada
    // — la sesión anterior queda intacta y NO se limpia la caché.
    await switchUniversidad(universidadId);
    await queryClient.cancelQueries();
    queryClient.clear();
  };

  const value: TenantContextValue = {
    universidadActivaId: user?.universidad_activa_id ?? null,
    rol: user?.rol ?? null,
    esSuperadmin: user?.es_superadmin ?? false,
    cambiarUniversidad,
  };

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>;
}
