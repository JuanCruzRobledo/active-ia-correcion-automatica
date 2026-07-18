import { apiClient } from '@/shared/services/api-client';
import { fetchWithAuth } from '@/shared/services/fetchWithAuth';
import type { EntregaMasivaResumen, PorEntregarResponse } from '../types';

export async function getPorEntregar(): Promise<PorEntregarResponse> {
  const { data } = await apiClient.get<PorEntregarResponse>('/por-entregar');
  return data;
}

export interface EntregarTodoHandlers {
  onTotal: (total: number) => void;
  onProgreso: (procesadas: number, total: number) => void;
  onResumen: (resumen: EntregaMasivaResumen) => void;
  onError: (mensaje: string) => void;
}

/**
 * Subida masiva con progreso en vivo (Server-Sent Events).
 * Usa fetch (axios no streamea bien) vía el helper compartido fetchWithAuth,
 * que resuelve baseURL + JWT; acá solo se lee el body por chunks.
 */
export async function entregarTodoStream(handlers: EntregarTodoHandlers): Promise<void> {
  let resp: Response;
  try {
    resp = await fetchWithAuth('/por-entregar/entregar/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
  } catch {
    handlers.onError('No se pudo conectar con el servidor.');
    return;
  }

  if (!resp.ok || !resp.body) {
    let detail = 'No se pudo iniciar la entrega masiva.';
    try {
      const body = await resp.json();
      detail = body?.detail ?? detail;
    } catch {
      /* respuesta sin JSON */
    }
    handlers.onError(detail);
    return;
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      let ev: Record<string, unknown>;
      try {
        ev = JSON.parse(line.slice(5).trim());
      } catch {
        continue;
      }
      switch (ev.tipo) {
        case 'inicio':
          handlers.onTotal(Number(ev.total ?? 0));
          break;
        case 'progreso':
          handlers.onProgreso(Number(ev.procesadas ?? 0), Number(ev.total ?? 0));
          break;
        case 'resumen':
          handlers.onResumen(ev as unknown as EntregaMasivaResumen);
          break;
        case 'error':
          handlers.onError(String(ev.detail ?? 'Error en la entrega masiva'));
          break;
      }
    }
  }
}
