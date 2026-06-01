import { apiClient } from '@/shared/services/api-client';
import type {
  ImportarMoodleRequest,
  ImportarMoodleResponse,
  MateriasPendientesResponse,
} from '../types';

export async function getPendientesMoodle(): Promise<MateriasPendientesResponse> {
  const { data } = await apiClient.get<MateriasPendientesResponse>('/pendientes/moodle');
  return data;
}

export async function importarMoodle(
  req: ImportarMoodleRequest,
): Promise<ImportarMoodleResponse> {
  // "Importar todo" puede descargar decenas de entregas desde Moodle.
  // El backend paraleliza las descargas, pero damos margen al timeout del cliente
  // (el default global de axios es 120s, insuficiente para volúmenes grandes).
  const { data } = await apiClient.post<ImportarMoodleResponse>('/moodle/importar', req, {
    timeout: 5 * 60 * 1000, // 5 minutos
  });
  return data;
}

export interface ImportStreamHandlers {
  onPreparando: (listos: number, total: number) => void;
  onTotal: (total: number) => void;
  onProgreso: (procesadas: number, total: number) => void;
  onResumen: (resumen: ImportarMoodleResponse) => void;
  onError: (mensaje: string) => void;
}

/**
 * Importación con progreso en vivo (Server-Sent Events).
 * Usa fetch (axios no streamea bien): manda el JWT por header y lee el body por chunks.
 */
export async function importarMoodleStream(
  req: ImportarMoodleRequest,
  handlers: ImportStreamHandlers,
): Promise<void> {
  const baseURL = apiClient.defaults.baseURL ?? '/api/v1';
  const token = localStorage.getItem('auth_token');

  let resp: Response;
  try {
    resp = await fetch(`${baseURL}/moodle/importar/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(req),
    });
  } catch {
    handlers.onError('No se pudo conectar con el servidor.');
    return;
  }

  if (!resp.ok || !resp.body) {
    let detail = 'No se pudo iniciar la importación.';
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
        case 'preparando':
          handlers.onPreparando(Number(ev.listos ?? 0), Number(ev.total ?? 0));
          break;
        case 'inicio':
          handlers.onTotal(Number(ev.total ?? 0));
          break;
        case 'progreso':
          handlers.onProgreso(Number(ev.procesadas ?? 0), Number(ev.total ?? 0));
          break;
        case 'resumen':
          handlers.onResumen(ev as unknown as ImportarMoodleResponse);
          break;
        case 'error':
          handlers.onError(String(ev.detail ?? 'Error en la importación'));
          break;
      }
    }
  }
}
