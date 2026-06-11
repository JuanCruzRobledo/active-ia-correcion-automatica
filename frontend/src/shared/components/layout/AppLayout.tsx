import { Outlet, ScrollRestoration } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { MobileHeader } from './MobileHeader';
import { BottomNav } from './BottomNav';

export const AppLayout = () => {
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
          <Outlet />
        </main>

        {/* Bottom tab bar - solo mobile, hermano del main */}
        <BottomNav className="lg:hidden" />
      </div>

      {/* Reset de scroll por ruta (sensación nativa al navegar) */}
      <ScrollRestoration />
    </div>
  );
};
