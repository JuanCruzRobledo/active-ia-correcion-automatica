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
  X,
  FileCode,
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

  // Fetch code content from backend
  const { data: contenido, isLoading, isError, error } = useEntregaContenido(entregaId);

  /**
   * Format number with thousand separators.
   */
  const formatNumber = (num: number): string => {
    return num.toLocaleString('es-AR');
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} size="2xl">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-border pb-4 mb-6">
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <FileCode className="h-5 w-5 text-accent" />
            <h2 className="text-xl font-semibold text-foreground">
              Código de Entrega
            </h2>
          </div>
          <div className="space-y-0.5">
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Alumno:</span> {alumno}
            </p>
            <p className="text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Archivo:</span> {archivoNombre}
            </p>
          </div>
        </div>

        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-foreground transition-colors"
          aria-label="Cerrar modal"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Content - Scrollable */}
      <div className="space-y-4 max-h-[calc(100vh-16rem)] overflow-y-auto pr-2">
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
            {/* Code Statistics */}
            <div className="grid grid-cols-3 gap-3">
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
            </div>

            {/* Included Files Section - Collapsible */}
            {contenido.archivos_incluidos.length > 0 && (
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

            {/* Code Container - Terminal/IDE Style */}
            <div className="border border-border rounded-lg overflow-hidden">
              {/* Code Header */}
              <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
                <div className="flex items-center gap-2">
                  <div className="flex gap-1.5">
                    <div className="w-3 h-3 rounded-full bg-red-500" />
                    <div className="w-3 h-3 rounded-full bg-yellow-500" />
                    <div className="w-3 h-3 rounded-full bg-green-500" />
                  </div>
                  <span className="text-xs font-mono text-gray-400 ml-2">
                    Código consolidado
                  </span>
                </div>
                <Badge variant="outline" className="bg-gray-700 text-gray-300 border-gray-600">
                  Read-only
                </Badge>
              </div>

              {/* Code Content - Scrollable */}
              <div className="bg-gray-900 max-h-[600px] overflow-auto">
                <pre className="p-4 text-sm leading-relaxed">
                  <code className="font-mono text-gray-100 whitespace-pre">
                    {contenido.contenido_consolidado}
                  </code>
                </pre>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Footer */}
      {!isLoading && !isError && (
        <div className="flex items-center justify-end gap-3 border-t border-border pt-4 mt-6">
          <Button variant="outline" onClick={onClose}>
            Cerrar
          </Button>
        </div>
      )}
    </Modal>
  );
}
