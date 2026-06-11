import { type ReactNode } from 'react';
import { Modal } from './Modal';
import { Button } from './Button';

export interface ConfirmDialogProps {
  /**
   * Controla la visibilidad del diálogo
   */
  isOpen: boolean;

  /**
   * Callback al cancelar o cerrar (X, Escape, backdrop si está habilitado)
   */
  onClose: () => void;

  /**
   * Callback al confirmar la acción. Tras ejecutarse, el diálogo NO se cierra
   * solo: el consumidor decide cuándo llamar a `onClose` (útil para esperar a
   * que termine una mutación antes de cerrar).
   */
  onConfirm: () => void;

  /**
   * Título del diálogo
   */
  title: string;

  /**
   * Mensaje / pregunta de confirmación. Acepta texto plano o nodos.
   */
  message: ReactNode;

  /**
   * Texto del botón de confirmación
   * @default 'Confirmar'
   */
  confirmLabel?: string;

  /**
   * Texto del botón de cancelar
   * @default 'Cancelar'
   */
  cancelLabel?: string;

  /**
   * Variante visual del botón de confirmación. Usar `destructive` para
   * acciones de borrado / peligrosas (rojo, igual que el resto de la app).
   * @default 'primary'
   */
  variant?: 'primary' | 'destructive' | 'success';

  /**
   * Muestra spinner y deshabilita los botones mientras la acción está en curso
   * @default false
   */
  isLoading?: boolean;
}

/**
 * Diálogo de confirmación construido sobre `Modal`. Reemplazo accesible y con
 * tokens (respeta dark mode) de `window.confirm`.
 *
 * En mobile se renderiza como bottom-sheet (heredado de `Modal`), en desktop
 * como diálogo centrado. Botones con touch target ≥44px en mobile (gracias a
 * `Button` con `w-full sm:w-auto`) y orden invertido en mobile para que la
 * acción primaria quede más accesible al pulgar.
 *
 * @example
 * ```tsx
 * const [open, setOpen] = useState(false);
 *
 * <ConfirmDialog
 *   isOpen={open}
 *   onClose={() => setOpen(false)}
 *   onConfirm={() => { eliminar(); setOpen(false); }}
 *   title="Eliminar tutor"
 *   message="¿Seguro que querés eliminar este tutor nexo? Esta acción no se puede deshacer."
 *   confirmLabel="Eliminar"
 *   variant="destructive"
 * />
 * ```
 */
export function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  variant = 'primary',
  isLoading = false,
}: ConfirmDialogProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="md"
      footer={
        <div className="flex w-full flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={isLoading}
            className="w-full sm:w-auto"
          >
            {cancelLabel}
          </Button>
          <Button
            variant={variant}
            onClick={onConfirm}
            isLoading={isLoading}
            className="w-full sm:w-auto"
          >
            {confirmLabel}
          </Button>
        </div>
      }
    >
      <p className="text-sm leading-relaxed text-muted-foreground">{message}</p>
    </Modal>
  );
}
