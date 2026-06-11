import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { QueryProvider } from './providers';
import { router } from './router';
import { useVersionCheck } from '@/shared/hooks/useVersionCheck';
import { ThemeProvider } from '@/shared/hooks/ThemeProvider';

const AppContent = () => {
  useVersionCheck();
  return (
    <RouterProvider router={router} />
  );
};

export const App = () => {
  return (
    <ThemeProvider>
      <QueryProvider>
        <AppContent />
        <Toaster
          position="top-right"
          // En la PWA (status bar black-translucent) el contenido se dibuja por debajo
          // de la barra de estado, asi que sin esto los toasts pisan el notch / Dynamic
          // Island / hora / bateria. Corremos el contenedor por debajo del safe-area:
          // en desktop/sin notch env()=0 → queda el gutter normal de 1rem (via max()).
          containerStyle={{
            top: 'max(1rem, calc(env(safe-area-inset-top) + 0.5rem))',
            right: 'max(1rem, env(safe-area-inset-right))',
            left: 'max(1rem, env(safe-area-inset-left))',
          }}
          toastOptions={{
            duration: 4000,
            style: {
              background: 'oklch(var(--card))',
              color: 'oklch(var(--card-foreground))',
              border: '1px solid oklch(var(--border))',
            },
            success: {
              iconTheme: {
                primary: 'oklch(var(--success))',
                secondary: 'oklch(var(--success-foreground))',
              },
            },
            error: {
              iconTheme: {
                primary: 'oklch(var(--destructive))',
                secondary: 'oklch(var(--destructive-foreground))',
              },
            },
          }}
        />
      </QueryProvider>
    </ThemeProvider>
  );
};
