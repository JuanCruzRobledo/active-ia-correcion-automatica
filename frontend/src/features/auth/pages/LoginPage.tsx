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

    loginMutation.mutate({ username, password });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-background px-4">
      <div className="w-full max-w-md space-y-8">
        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-foreground">Active-IA</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Sistema de Corrección Automática
          </p>
        </div>

        {/* Form Card */}
        <div className="bg-card rounded-lg shadow-sm border border-border p-8">
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
                autoFocus
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
