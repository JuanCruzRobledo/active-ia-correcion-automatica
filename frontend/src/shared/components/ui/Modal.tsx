import { useEffect, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface ModalProps {
  /**
   * Controls modal visibility
   */
  isOpen: boolean;

  /**
   * Callback when modal should close
   */
  onClose: () => void;

  /**
   * Modal title
   */
  title?: string;

  /**
   * Modal content
   */
  children: ReactNode;

  /**
   * Footer content (typically buttons)
   */
  footer?: ReactNode;

  /**
   * Size variant
   * - sm: max-w-sm
   * - md: max-w-md
   * - lg: max-w-lg
   * - xl: max-w-xl
   * - 2xl: max-w-2xl (default)
   * - full: max-w-full
   */
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full';

  /**
   * Prevent closing on backdrop click (default: true)
   */
  disableBackdropClose?: boolean;

  /**
   * Prevent closing on Escape key
   */
  disableEscapeClose?: boolean;

  /**
   * Additional class for modal content
   */
  className?: string;
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-xl',
  '2xl': 'max-w-2xl',
  full: 'max-w-full',
};

/**
 * Modal dialog component with backdrop and focus trap.
 *
 * @example
 * ```tsx
 * const [isOpen, setIsOpen] = useState(false);
 *
 * <Modal
 *   isOpen={isOpen}
 *   onClose={() => setIsOpen(false)}
 *   title="Confirmar eliminación"
 *   footer={
 *     <>
 *       <Button variant="outline" onClick={() => setIsOpen(false)}>
 *         Cancelar
 *       </Button>
 *       <Button variant="destructive" onClick={handleDelete}>
 *         Eliminar
 *       </Button>
 *     </>
 *   }
 * >
 *   ¿Estás seguro de que deseas eliminar este usuario?
 * </Modal>
 * ```
 */
export function Modal({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = '2xl',
  disableBackdropClose = true,
  disableEscapeClose = false,
  className,
}: ModalProps) {
  // Handle Escape key
  useEffect(() => {
    if (!isOpen || disableEscapeClose) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, disableEscapeClose, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (disableBackdropClose) return;
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const modalContent = (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onClick={handleBackdropClick}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      <div
        className={cn(
          'relative w-full bg-card rounded-lg shadow-lg border border-border',
          'flex flex-col max-h-[90vh]',
          sizeClasses[size],
          // Animation
          'animate-in fade-in-0 zoom-in-95 duration-200',
          className
        )}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-border">
          {title && (
            <h2
              id="modal-title"
              className="text-xl font-semibold text-foreground"
            >
              {title}
            </h2>
          )}
          <button
            onClick={onClose}
            className="ml-auto rounded-md p-1 text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            aria-label="Cerrar modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {children}
        </div>

        {/* Footer */}
        {footer && (
          <div className="flex items-center justify-end gap-2 p-6 border-t border-border">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
