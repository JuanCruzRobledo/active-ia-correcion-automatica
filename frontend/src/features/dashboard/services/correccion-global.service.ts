// features/dashboard/services/correccion-global.service.ts
/**
 * Service para la corrección masiva global (Fase 4 — API key paga).
 */

import { apiClient } from '@/shared/services/api-client';

export interface ProgresoGlobal {
  subidas: number;
  pendientes: number;
  corregidas: number;
  error: number;
  total: number;
  /** Desglose de las entregas en ERROR por código (item #7), para el resumen. */
  errores_por_codigo?: Record<string, number>;
}

export interface CorregirGlobalResponse {
  mensaje: string;
  total_encoladas: number;
}

export async function getProgresoGlobal(): Promise<ProgresoGlobal> {
  const { data } = await apiClient.get<ProgresoGlobal>('/correcciones/global/progreso');
  return data;
}

export async function corregirGlobal(): Promise<CorregirGlobalResponse> {
  const { data } = await apiClient.post<CorregirGlobalResponse>('/correcciones/global');
  return data;
}
