import { useState } from 'react';
import type { FormEvent } from 'react';
import { AxiosError } from 'axios';
import { useLogin } from '../hooks/useLogin';
import { useSeleccionarUniversidad } from '../hooks/useSeleccionarUniversidad';
import { SeleccionUniversidadStep } from '../components/SeleccionUniversidadStep';
import { Button } from '@/shared/components/ui/Button';
import { Input } from '@/shared/components/ui/Input';
import { getErrorMessage } from '@/shared/types';

/** Extrae el mensaje real del backend de un error de mutación (AxiosError → detail). */
function mensajeDeError(error: unknown): string | null {
  if (!error) return null;
  const data = error instanceof AxiosError ? error.response?.data : undefined;
  return getErrorMessage(data ?? error);
}

export const LoginPage = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [tokenVencidoMsg, setTokenVencidoMsg] = useState<string | null>(null);
  const loginMutation = useLogin();
  const seleccionMutation = useSeleccionarUniversidad();

  // Rama de selección: el login devolvió `requiere_seleccion` en vez del token final.
  const seleccion =
    loginMutation.data && 'requiere_seleccion' in loginMutation.data
      ? loginMutation.data
      : null;

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!username || !password) {
      return;
    }

    // Cerrar el teclado de iOS antes de navegar: si sigue abierto cuando entra el
    // AppLayout, el BottomNav (position:fixed) queda mal posicionado. El blur arranca
    // el cierre del teclado mientras corre el request de login.
    (document.activeElement as HTMLElement | null)?.blur();

    setTokenVencidoMsg(null);
    loginMutation.mutate({ username, password });
  };

  const handleVolver = () => {
    loginMutation.reset();
    seleccionMutation.reset();
    setTokenVencidoMsg(null);
  };

  const handleElegirUniversidad = (universidadId: number) => {
    if (!seleccion) return;
    seleccionMutation.mutate(
      { tokenTransicion: seleccion.token_transicion, universidadId },
      {
        onError: (error) => {
          // Token de transición vencido: el backend responde 401. Volvemos al
          // formulario con un mensaje que invita a reintentar (no queda al
          // usuario varado en la pantalla de selección).
          const status = error instanceof AxiosError ? error.response?.status : undefined;
          if (status === 401) {
            loginMutation.reset();
            seleccionMutation.reset();
            setTokenVencidoMsg('Tardaste demasiado en elegir. Volvé a intentar iniciar sesión.');
          }
        },
      }
    );
  };

  if (seleccion) {
    return (
      <SeleccionUniversidadStep
        seleccion={seleccion}
        isPending={seleccionMutation.isPending}
        errorMessage={
          seleccionMutation.isError
            ? mensajeDeError(seleccionMutation.error) ?? 'Error al seleccionar la universidad.'
            : null
        }
        onElegir={handleElegirUniversidad}
        onVolver={handleVolver}
      />
    );
  }

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
            {tokenVencidoMsg && (
              <div className="rounded-lg border border-warning bg-warning/10 p-4 text-sm text-warning">
                {tokenVencidoMsg}
              </div>
            )}

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
                {mensajeDeError(loginMutation.error) ??
                  'Error al iniciar sesión. Verifica tus credenciales.'}
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
