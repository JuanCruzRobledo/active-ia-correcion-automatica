import { RouterProvider } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { QueryProvider } from './providers';
import { router } from './router';
import { useVersionCheck } from '@/shared/hooks/useVersionCheck';

const AppContent = () => {
  useVersionCheck();
  return (
    <RouterProvider router={router} />
  );
};

export const App = () => {
  return (
    <QueryProvider>
      <AppContent />
      <Toaster
        position="top-right"
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
  );
};
