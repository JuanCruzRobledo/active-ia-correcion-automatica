import { useState } from 'react';
import type { FormEvent } from 'react';
import { useLogin } from '../hooks/useLogin';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';

export const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const loginMutation = useLogin();

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!username || !password) {
      return;
    }

    // Cerrar el teclado de iOS antes de navegar: si sigue abierto cuando entra el
    // AppLayout, el BottomNav (position:fixed) queda mal posicionado. El blur arranca
    // el cierre del teclado mientras corre el request de login.
    (document.activeElement as HTMLElement | null)?.blur();

    loginMutation.mutate({ username, password });
  };

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background pt-safe pb-safe pl-safe pr-safe px-4 py-8 overflow-y-auto scroll-momentum">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <img
              src="/active-ia-logo.svg"
              alt="Active-IA Logo"
              className="h-20 w-20"
            />
          </div>
          <h1 className="text-3xl font-bold text-foreground">Active-IA</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sistema de Corrección Automática
          </p>
        </div>

        {/* Form Card: edge-to-edge en mobile, card centrada en sm: */}
        <div className="bg-card rounded-none sm:rounded-lg shadow-sm border border-border p-6 sm:p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="space-y-4">
              {/* Username Input */}
              <Input
                label="Usuario"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Ingresa tu usuario"
                disabled={loginMutation.isPending}
                required
                autoComplete="username"
                inputMode="text"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />

              {/* Password Input */}
              <Input
                label="Contraseña"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Ingresa tu contraseña"
                disabled={loginMutation.isPending}
                required
                autoComplete="current-password"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />
            </div>

            {/* Error Message */}
            {loginMutation.isError && (
              <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
                {loginMutation.error instanceof Error
                  ? loginMutation.error.message
                  : 'Error al iniciar sesión. Verifica tus credenciales.'}
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              disabled={loginMutation.isPending || !username || !password}
              isLoading={loginMutation.isPending}
            >
              {loginMutation.isPending ? 'Iniciando sesión...' : 'Iniciar sesión'}
            </Button>
          </form>
        </div>

        {/* Footer */}
        <div className="text-center text-sm text-muted-foreground">
          <p>
            ¿Olvidaste tu contraseña? Contacta al administrador.
          </p>
        </div>
      </div>
    </div>
  );
};
