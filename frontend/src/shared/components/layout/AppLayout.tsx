import { useEffect, Suspense } from 'react';
import { Outlet, ScrollRestoration } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { MobileHeader } from './MobileHeader';
import { BottomNav } from './BottomNav';
import { LoadingState } from '@/shared/components/ui';

export const AppLayout = () => {
  // Al loguearse se entra al shell desde /login, donde el teclado de iOS pudo dejar
  // la ventana scrolleada. Ese scroll residual deja el BottomNav (position:fixed) mal
  // ubicado ("se va para arriba") hasta que un gesto fuerza el reflow. Soltamos el foco
  // y reseteamos el scroll al montar el shell para que la barra quede abajo de una.
  useEffect(() => {
    (document.activeElement as HTMLElement | null)?.blur();
    window.scrollTo(0, 0);
  }, []);

  return (
    // h-[100dvh]: la barra de URL móvil rompe `h-screen`; dvh sigue al viewport visible.
    <div className="flex h-[100dvh] bg-background">
      {/* Sidebar - solo desktop */}
      <Sidebar />

      {/* Área de contenido */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Header mobile - simplificado, ya no es navegación principal */}
        <MobileHeader />

        {/* Contenido con scroll. En mobile reservamos espacio inferior para la
            bottom-nav + home indicator; en desktop vuelve al padding original. */}
        <main className="flex-1 overflow-y-auto overscroll-contain px-4 py-4 pb-[calc(4rem+env(safe-area-inset-bottom))] sm:p-6 lg:p-8 lg:pb-8">
          {/* PERF-014: boundary único para las páginas lazy-loaded (ver router.tsx). */}
          <Suspense fallback={<LoadingState title="Cargando…" />}>
            <Outlet />
          </Suspense>
        </main>

        {/* Bottom tab bar - solo mobile, hermano del main */}
        <BottomNav className="lg:hidden" />
      </div>

      {/* Reset de scroll por ruta (sensación nativa al navegar) */}
      <ScrollRestoration />
    </div>
  );
};
