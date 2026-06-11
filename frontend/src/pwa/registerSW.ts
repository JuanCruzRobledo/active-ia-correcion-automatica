import { registerSW as registerVitePWA } from 'virtual:pwa-register';

/**
 * Callbacks opcionales para conectar el ciclo de vida del Service Worker
 * con la UI (toast de actualizacion, aviso de listo-offline).
 */
export interface RegisterPwaOptions {
  /**
   * Se dispara cuando hay una version nueva esperando. Recibe `updateSW`,
   * que al llamarse con `true` activa el SW nuevo y recarga la app.
   */
  onNeedRefresh?: (updateSW: (reloadPage?: boolean) => Promise<void>) => void;
  /** Se dispara cuando la app quedo precacheada y lista para usarse sin conexion. */
  onOfflineReady?: () => void;
}

/**
 * Registra el Service Worker (generado por vite-plugin-pwa en build).
 * En desarrollo `devOptions.enabled = false`, por lo que el SW no se registra
 * y esta funcion es un no-op seguro.
 *
 * Devuelve la funcion `updateSW` por si se quiere forzar la actualizacion
 * desde otro punto de la app.
 */
export function registerSW(
  options: RegisterPwaOptions = {},
): (reloadPage?: boolean) => Promise<void> {
  const updateSW = registerVitePWA({
    immediate: true,
    onNeedRefresh() {
      options.onNeedRefresh?.(updateSW);
    },
    onOfflineReady() {
      options.onOfflineReady?.();
    },
  });

  return updateSW;
}
