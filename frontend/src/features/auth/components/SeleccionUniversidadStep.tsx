import { Button } from '@/shared/components/ui/Button';
import type { SeleccionUniversidadRequerida } from '@/shared/types';

interface SeleccionUniversidadStepProps {
  seleccion: SeleccionUniversidadRequerida;
  isPending: boolean;
  errorMessage: string | null;
  onElegir: (universidadId: number) => void;
  onVolver: () => void;
}

/**
 * Segundo paso del login en dos pasos (Fase 5 multi-tenant): lista de
 * universidades disponibles (nombre + rol) con opción de volver al formulario
 * descartando el `token_transicion`.
 *
 * Ref: openspec/changes/multi-tenant-frontend-workspace/specs/frontend-login-dos-pasos/spec.md
 */
export const SeleccionUniversidadStep = ({
  seleccion,
  isPending,
  errorMessage,
  onElegir,
  onVolver,
}: SeleccionUniversidadStepProps) => {
  return (
    <div className="min-h-dvh flex items-center justify-center bg-background pt-safe pb-safe pl-safe pr-safe px-4 py-8 overflow-y-auto scroll-momentum">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <img src="/active-ia-logo.svg" alt="Active-IA Logo" className="h-20 w-20" />
          </div>
          <h1 className="text-2xl font-bold text-foreground">Elegí tu universidad</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Tenés acceso a más de una universidad. Elegí con cuál querés trabajar.
          </p>
        </div>

        <div className="bg-card rounded-none sm:rounded-lg shadow-sm border border-border p-6 sm:p-8 space-y-3">
          {seleccion.universidades.map((u) => (
            <button
              key={u.id}
              type="button"
              onClick={() => onElegir(u.id)}
              disabled={isPending}
              className="w-full flex items-center justify-between rounded-lg border border-border px-4 py-3 text-left transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              <span className="font-medium text-foreground">{u.nombre}</span>
              <span className="text-xs uppercase text-muted-foreground">{u.rol}</span>
            </button>
          ))}

          {errorMessage && (
            <div className="rounded-lg border border-destructive bg-destructive/10 p-4 text-sm text-destructive">
              {errorMessage}
            </div>
          )}

          <Button
            type="button"
            variant="ghost"
            className="w-full"
            onClick={onVolver}
            disabled={isPending}
          >
            Volver
          </Button>
        </div>
      </div>
    </div>
  );
};
