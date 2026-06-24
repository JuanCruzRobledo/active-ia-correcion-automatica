import { RefreshCw } from 'lucide-react';

interface NovedadesBannerProps {
  /** Mensaje ya resuelto según el rol (ver mensajeNovedades). */
  mensaje: string;
  /** Refresca la pantalla y oculta el aviso. */
  onActualizar: () => void;
}

/**
 * Aviso "hay novedades" (item #2, Capa B). No reemplaza los datos en pantalla: solo
 * ofrece actualizar cuando el backend cambió, para no interrumpir al usuario.
 */
export function NovedadesBanner({ mensaje, onActualizar }: NovedadesBannerProps) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-primary/30 bg-primary/10 px-4 py-2 text-sm">
      <span className="font-medium text-foreground">{mensaje}</span>
      <button
        type="button"
        onClick={onActualizar}
        className="flex shrink-0 cursor-pointer items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground transition-colors hover:bg-primary/90"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Actualizar
      </button>
    </div>
  );
}
