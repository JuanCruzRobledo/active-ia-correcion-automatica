/**
 * Estado de carga prominente para áreas de contenido: un anillo animado grande,
 * centrado, con un título y un subtítulo opcional que le dan contexto a la espera
 * (qué se está cargando / que puede tardar). Reemplaza la "ruedita chica" perdida
 * en una pantalla en blanco.
 */

export interface LoadingStateProps {
  /** Mensaje principal (ej: "Cargando entregas…"). */
  title?: string;
  /** Texto secundario opcional (ej: "Consultando Moodle, puede tardar unos segundos."). */
  subtitle?: string;
}

export function LoadingState({ title = 'Cargando…', subtitle }: LoadingStateProps) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-5 p-6 text-center">
      {/* Spinner grande: pista tenue + arco de color que gira (animación visible). */}
      <div
        role="status"
        aria-label="Cargando"
        className="h-16 w-16 animate-spin rounded-full border-4 border-primary/20 border-t-primary"
      />

      <div className="space-y-1">
        <p className="text-base font-medium text-foreground">{title}</p>
        {subtitle && <p className="text-sm text-muted-foreground">{subtitle}</p>}
      </div>
    </div>
  );
}
