import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import toast from 'react-hot-toast';
import './index.css';
import { App } from './app/App';
import { registerSW } from './pwa/registerSW';
import { OfflineBanner } from './pwa/OfflineBanner';

// Cuando el browser tiene el index.html viejo y trata de cargar un chunk
// que ya no existe (deploy nuevo), Vite dispara este evento.
// Forzamos reload para que el browser descargue el index.html actualizado.
// Se mantiene como fallback complementario al ciclo de update del Service Worker.
window.addEventListener('vite:preloadError', () => {
  window.location.reload();
});

// Registro del Service Worker (PWA). En dev es no-op (devOptions deshabilitado).
// onNeedRefresh: hay una version nueva esperando -> toast persistente para
// que el usuario decida actualizar. onOfflineReady: la app quedo cacheada.
registerSW({
  onNeedRefresh(updateSW) {
    toast(
      (t) => (
        <span className="flex items-center gap-3">
          Hay una nueva version
          <button
            type="button"
            className="rounded-md bg-primary px-3 py-1 text-sm font-medium text-primary-foreground"
            onClick={() => {
              toast.dismiss(t.id);
              void updateSW(true);
            }}
          >
            Actualizar
          </button>
        </span>
      ),
      { duration: Infinity, id: 'pwa-update' },
    );
  },
  onOfflineReady() {
    toast.success('Listo para usar sin conexion');
  },
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
    <OfflineBanner />
  </StrictMode>
);
