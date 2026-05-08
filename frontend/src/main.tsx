import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import { App } from './app/App';

// Cuando el browser tiene el index.html viejo y trata de cargar un chunk
// que ya no existe (deploy nuevo), Vite dispara este evento.
// Forzamos reload para que el browser descargue el index.html actualizado.
window.addEventListener('vite:preloadError', () => {
  window.location.reload();
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);