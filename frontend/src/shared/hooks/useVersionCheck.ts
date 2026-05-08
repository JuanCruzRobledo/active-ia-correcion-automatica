import { useEffect, useRef } from 'react';

const CHECK_INTERVAL_MS = 5 * 60 * 1000; // cada 5 minutos

/**
 * Detecta si se deployó una versión nueva comparando el ETag del index.html.
 * Si hay una versión nueva, recarga la página automáticamente.
 * Solo se activa cuando la tab está visible para no generar requests innecesarios.
 */
export function useVersionCheck() {
  const etagRef = useRef<string | null>(null);

  useEffect(() => {
    const check = async () => {
      if (document.visibilityState !== 'visible') return;

      try {
        const res = await fetch('/', { method: 'HEAD', cache: 'no-store' });
        const etag = res.headers.get('etag') ?? res.headers.get('last-modified');
        if (!etag) return;

        if (etagRef.current === null) {
          etagRef.current = etag;
          return;
        }

        if (etagRef.current !== etag) {
          window.location.reload();
        }
      } catch {
        // Sin conexión — no hacer nada
      }
    };

    const interval = setInterval(check, CHECK_INTERVAL_MS);
    document.addEventListener('visibilitychange', check);

    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', check);
    };
  }, []);
}
