import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/shared/services/api-client';

export type RecursoNovedades = 'entregas' | 'rubricas';

interface UseNovedadesOptions {
  enabled?: boolean;
  /** Cada cuánto poolear el token de versión (default 45s). */
  intervalMs?: number;
}

async function fetchVersiones(): Promise<Record<string, string>> {
  const { data } = await apiClient.get<Record<string, string>>('/sync/version');
  return data;
}

/**
 * Detecta cambios en el backend para un recurso (item #2, Capa B) sin reemplazar los
 * datos que el usuario está viendo. Poolea un token barato (MAX(updated_at)|COUNT) y,
 * cuando cambia respecto al renderizado, expone `hayNovedades=true` para mostrar un aviso.
 *
 * La primera lectura fija el baseline (no avisa). `aceptar()` se llama después de refrescar
 * la pantalla: re-fija el baseline al valor actual y oculta el aviso.
 */
export function useNovedades(
  recurso: RecursoNovedades,
  { enabled = true, intervalMs = 45000 }: UseNovedadesOptions = {}
) {
  const baselineRef = useRef<string | null>(null);
  const [hayNovedades, setHayNovedades] = useState(false);

  const query = useQuery({
    queryKey: ['sync-version'],
    queryFn: fetchVersiones,
    refetchInterval: intervalMs,
    refetchIntervalInBackground: false,
    enabled,
    staleTime: 0,
  });

  const actual = query.data?.[recurso];

  useEffect(() => {
    if (actual == null) return;
    if (baselineRef.current == null) {
      baselineRef.current = actual; // primera lectura = baseline; no dispara aviso
      return;
    }
    if (actual !== baselineRef.current) {
      setHayNovedades(true);
    }
  }, [actual]);

  const aceptar = () => {
    if (actual != null) baselineRef.current = actual;
    setHayNovedades(false);
  };

  return { hayNovedades, aceptar };
}
