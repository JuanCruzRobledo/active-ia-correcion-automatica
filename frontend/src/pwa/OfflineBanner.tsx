import { useEffect, useState } from 'react';
import { WifiOff } from 'lucide-react';

/**
 * Barra fija inferior que aparece cuando el dispositivo pierde conexion.
 * Escucha los eventos `online`/`offline` del navegador y respeta el
 * safe-area inset inferior (notch / barra de gestos en mobile).
 */
export function OfflineBanner() {
  const [offline, setOffline] = useState<boolean>(
    () => typeof navigator !== 'undefined' && navigator.onLine === false,
  );

  useEffect(() => {
    const goOnline = () => setOffline(false);
    const goOffline = () => setOffline(true);

    window.addEventListener('online', goOnline);
    window.addEventListener('offline', goOffline);

    return () => {
      window.removeEventListener('online', goOnline);
      window.removeEventListener('offline', goOffline);
    };
  }, []);

  if (!offline) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed bottom-0 inset-x-0 z-50 pb-[env(safe-area-inset-bottom)] bg-warning text-warning-foreground shadow-lg"
    >
      <div className="flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium">
        <WifiOff className="h-4 w-4" aria-hidden="true" />
        Sin conexion
      </div>
    </div>
  );
}
