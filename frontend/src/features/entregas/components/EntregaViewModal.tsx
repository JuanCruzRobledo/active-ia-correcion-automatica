// features/entregas/components/EntregaViewModal.tsx
/**
 * Professional modal component for viewing student submission code.
 *
 * Features:
 * - Read-only code viewer with syntax highlighting
 * - Displays list of included files (collapsible)
 * - Shows code statistics (lines, characters)
 * - Terminal/IDE-style dark code container
 * - Loading and error states
 * - Scrollable code container with max height
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md
 * Ref: docs/specs/03-REQUISITOS-FUNCIONALES.md section 7
 */

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Hash,
  Type,
  AlertCircle,
} from 'lucide-react';
import { Modal } from '../../../shared/components/ui/Modal';
import { Button } from '../../../shared/components/ui/Button';
import { Spinner } from '../../../shared/components/ui/Spinner';
import { Badge } from '../../../shared/components/ui/Badge';
import { useEntregaContenido } from '../hooks/useEntregas';

interface EntregaViewModalProps {
  /** ID of the entrega to display */
  entregaId: number;
  /** Student name for display */
  alumno: string;
  /** File name for display */
  archivoNombre: string;
  /** Modal open state */
  isOpen: boolean;
  /** Callback when modal closes */
  onClose: () => void;
}

/**
 * Modal for viewing student submission code in read-only mode.
 *
 * Fetches content from backend and displays it with syntax highlighting.
 */
export default function EntregaViewModal({
  entregaId,
  alumno,
  archivoNombre,
  isOpen,
  onClose,
}: EntregaViewModalProps) {
  const [isFilesExpanded, setIsFilesExpanded] = useState(true);
  const [isCodeExpanded, setIsCodeExpanded] = useState(false);

  // Fetch code content from backend
  const { data: contenido, isLoading, isError, error } = useEntregaContenido(entregaId);

  // Determine if we should show preview mode (only applies to code, not PDF)
  const PREVIEW_LENGTH = 1000; // characters
  const isPdf = contenido?.es_pdf ?? false;
  const shouldShowPreview =
    !isPdf &&
    contenido &&
    (contenido.contenido_consolidado?.length ?? 0) > PREVIEW_LENGTH &&
    !isCodeExpanded;

  const displayContent = shouldShowPreview
    ? contenido!.contenido_consolidado!.substring(0, PREVIEW_LENGTH) + '\n\n...'
    : contenido?.contenido_consolidado;

  // Check if content is limited (old entregas with only preview)
  const isLimitedContent = contenido && contenido.total_caracteres < 600; // Likely just preview

  /**
   * Format number with thousand separators.
   */
  const formatNumber = (num: number): string => {
    return num.toLocaleString('es-AR');
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl" title="Código de Entrega">
      {/* Info and Statistics - No scrollable */}
      <div className="border-b border-border pb-4 mb-4 -mt-6">
        <div className="space-y-0.5 mb-4">
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Alumno:</span> {alumno}
          </p>
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground">Archivo:</span> {archivoNombre}
          </p>
        </div>

        {/* Statistics Cards - In Header */}
        {contenido && (
          <div className={`grid gap-3 ${contenido.archivos_incluidos.length > 1 ? 'grid-cols-3' : 'grid-cols-2'}`}>
            {/* Only show Archivos card if more than 1 file (ZIP case) */}
            {contenido.archivos_incluidos.length > 1 && (
              <div className="bg-muted/50 rounded-lg p-3 border border-border">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="h-4 w-4 text-muted-foreground" />
                  <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Archivos
                  </span>
                </div>
                <div className="text-xl font-bold text-foreground">
                  {contenido.archivos_incluidos.length}
                </div>
              </div>
            )}

            {/* Only show Lines/Chars cards for code submissions, not PDFs */}
            {!isPdf && (
              <>
                <div className="bg-muted/50 rounded-lg p-3 border border-border">
                  <div className="flex items-center gap-2 mb-1">
                    <Hash className="h-4 w-4 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Líneas
                    </span>
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {formatNumber(contenido.total_lineas)}
                  </div>
                </div>

                <div className="bg-muted/50 rounded-lg p-3 border border-border">
                  <div className="flex items-center gap-2 mb-1">
                    <Type className="h-4 w-4 text-muted-foreground" />
                    <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                      Caracteres
                    </span>
                  </div>
                  <div className="text-xl font-bold text-foreground">
                    {formatNumber(contenido.total_caracteres)}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Content - Single Scrollable Area */}
      <div className="space-y-4 max-h-[calc(100vh-22rem)] overflow-y-auto pr-2">
        {/* Loading State */}
        {isLoading && (
          <div className="flex items-center justify-center py-12">
            <Spinner size="lg" label="Cargando código..." />
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="flex flex-col items-center justify-center py-12 px-4">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-destructive/10 mb-4">
              <AlertCircle className="h-8 w-8 text-destructive" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">
              Error al cargar el código
            </h3>
            <p className="text-sm text-muted-foreground text-center max-w-md">
              {error?.message || 'Ocurrió un error al obtener el contenido de la entrega.'}
            </p>
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="mt-4"
            >
              Cerrar
            </Button>
          </div>
        )}

        {/* Success State - Show Content */}
        {contenido && (
          <>
            {/* Included Files Section - Collapsible */}
            {!isPdf && contenido.archivos_incluidos.length > 0 && (
              <div className="border border-border rounded-lg overflow-hidden">
                <button
                  onClick={() => setIsFilesExpanded(!isFilesExpanded)}
                  className="w-full flex items-center justify-between p-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    {isFilesExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                    <span className="text-sm font-medium text-foreground">
                      Archivos Incluidos
                    </span>
                    <Badge variant="outline">
                      {contenido.archivos_incluidos.length}
                    </Badge>
                  </div>
                </button>

                {isFilesExpanded && (
                  <div className="p-3 bg-background border-t border-border">
                    <div className="grid grid-cols-2 gap-2 max-h-32 overflow-y-auto">
                      {contenido.archivos_incluidos.map((archivo, index) => (
                        <div
                          key={index}
                          className="flex items-center gap-2 text-xs text-muted-foreground bg-muted/20 rounded px-2 py-1.5 font-mono"
                        >
                          <FileText className="h-3 w-3 flex-shrink-0" />
                          <span className="truncate" title={archivo}>
                            {archivo}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Warning for limited content */}
            {!isPdf && isLimitedContent && (
              <div className="bg-warning/10 border border-warning/30 rounded-lg p-3 flex items-start gap-2">
                <AlertCircle className="h-5 w-5 text-warning flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-foreground">Vista Limitada</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Solo se muestran los primeros 500 caracteres. Para ver el código completo, re-sube esta entrega.
                  </p>
                </div>
              </div>
            )}

            {/* Content Display: PDF vs Code */}
            <div className="border border-border rounded-lg overflow-hidden">
              {/* Header */}
              <div className="flex items-center justify-between px-4 py-2 bg-muted border-b border-border">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-destructive" />
                    <div className="w-3 h-3 rounded-full bg-warning" />
                    <div className="w-3 h-3 rounded-full bg-success" />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground ml-2">
                    {isPdf
                      ? 'Visor de PDF'
                      : isLimitedContent
                        ? 'Código (preview)'
                        : 'Código procesado'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {!isLimitedContent && shouldShowPreview && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setIsCodeExpanded(!isCodeExpanded)}
                      className="text-xs h-7"
                    >
                      {isCodeExpanded ? 'Ver menos' : 'Ver todo'}
                    </Button>
                  )}
                  <span className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80">Read-only</span>
                </div>
              </div>

              {/* Viewer Area */}
              <div className="bg-muted/30">
                {isPdf ? (
                  contenido.pdf_contenido_b64 ? (
                    <iframe
                      src={`data:application/pdf;base64,${contenido.pdf_contenido_b64}`}
                      className="w-full h-[60vh] border-0"
                      title="Visor de entrega PDF"
                    />
                  ) : (
                    <div className="flex flex-col items-center justify-center h-48 px-4 text-center">
                      <AlertCircle className="h-8 w-8 text-muted-foreground mb-3" />
                      <p className="text-sm font-medium text-foreground">
                        Contenido no disponible
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        El archivo PDF no pudo ser recuperado.
                      </p>
                    </div>
                  )
                ) : (
                  <pre className="p-4 text-sm leading-relaxed overflow-x-auto">
                    <code className="font-mono text-foreground whitespace-pre">
                      {displayContent}
                    </code>
                  </pre>
                )}
              </div>

              {/* Expand Button at Bottom (Only for Code) */}
              {!isLimitedContent && shouldShowPreview && !isPdf && (
                <div className="border-t border-border bg-muted/50 px-4 py-2 text-center">
                  <button
                    onClick={() => setIsCodeExpanded(true)}
                    className="text-sm text-accent hover:text-accent/80 font-medium transition-colors"
                  >
                    Ver{' '}
                    {formatNumber(
                      contenido.total_caracteres - PREVIEW_LENGTH
                    )}{' '}
                    caracteres más...
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}
