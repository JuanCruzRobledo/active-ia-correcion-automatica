import { RefreshCw } from 'lucide-react';

interface RefreshButtonProps {
  /** Dispara el refetch de la pantalla. */
  onRefresh: () => void;
  /** Mientras true, muestra el spinner y deshabilita el botón. */
  isRefreshing?: boolean;
  /** Texto del botón (default "Actualizar"). En mobile solo se ve el ícono. */
  label?: string;
  className?: string;
}

/**
 * Botón "Actualizar" compartido. Misma estética que el de Pendientes (el que el
 * usuario aprobó) para que el refresco manual se vea igual en todas las pantallas.
 */
export function RefreshButton({
  onRefresh,
  isRefreshing = false,
  label = 'Actualizar',
  className = '',
}: RefreshButtonProps) {
  return (
    <button
      type="button"
      onClick={onRefresh}
      disabled={isRefreshing}
      aria-label={label}
      className={`flex min-h-11 cursor-pointer items-center justify-center gap-2 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50 ${className}`}
    >
      <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
      <span className="hidden sm:inline">{isRefreshing ? 'Actualizando…' : label}</span>
    </button>
  );
}
