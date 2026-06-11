import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from 'react';
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
   * Variante mobile full-screen para formularios largos.
   * En mobile ocupa todo el alto (`h-[100dvh]`, sin radios) en lugar de
   * comportarse como bottom-sheet. En desktop (sm:) no cambia nada: sigue
   * siendo el diálogo centrado de siempre.
   * @default false
   */
  fullScreen?: boolean;

  /**
   * Additional class for modal content
   */
  className?: string;
}

const sizeClasses = {
  sm: 'sm:max-w-sm',
  md: 'sm:max-w-md',
  lg: 'sm:max-w-lg',
  xl: 'sm:max-w-xl',
  '2xl': 'sm:max-w-2xl',
  full: 'sm:max-w-full',
};

// Easing iOS para el deslizamiento del bottom-sheet (mismo que usa Sheet).
const IOS_EASE = 'cubic-bezier(0.32,0.72,0,1)';
// Píxeles de arrastre vertical a partir de los cuales el swipe-down cierra.
const SWIPE_CLOSE_THRESHOLD = 90;
// Duración de la animación de entrada/salida (debe coincidir con el timeout de desmontaje).
const ANIM_MS = 260;

/**
 * Modal dialog con backdrop y animación app-like.
 *
 * Responsive:
 * - **Mobile (clases base)**: BOTTOM-SHEET deslizable. Animación de entrada/salida
 *   slide-up/slide-down con easing iOS, swipe-down sobre el drag handle para cerrar,
 *   y SIN botón X (el handle + swipe + backdrop son la affordance nativa). Con
 *   `fullScreen` ocupa toda la pantalla y conserva la X (única forma de cerrar).
 * - **Desktop (`sm:`)**: diálogo centrado con fade + scale sutil. La X se mantiene.
 *
 * La animación es autocontenida (transform/opacity inline + máquina de estados
 * mounted/visible), no depende de utilidades CSS externas. La API pública se mantiene
 * 100% compatible.
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
  fullScreen = false,
  className,
}: ModalProps) {
  // `mounted` mantiene el nodo en el DOM durante la animación de salida.
  const [mounted, setMounted] = useState(isOpen);
  // `visible` dispara la transición de entrada en el frame siguiente al montaje.
  const [visible, setVisible] = useState(false);
  // Arrastre vertical (swipe-down) del bottom-sheet en mobile.
  const [dragY, setDragY] = useState(0);
  const [dragging, setDragging] = useState(false);
  // La animación difiere por viewport (translate en mobile, scale en desktop) y los
  // estilos inline no entienden breakpoints → se resuelve con matchMedia.
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(max-width: 639px)').matches
  );

  const panelRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef<number | null>(null);

  // Seguir el viewport (orientación / resize con el modal abierto).
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 639px)');
    const handler = () => setIsMobile(mq.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Montaje inmediato al abrir (ajuste de estado en render, patrón válido) para que el
  // portal exista en el mismo frame y la animación de entrada pueda dispararse.
  if (isOpen && !mounted) {
    setMounted(true);
  }

  // Entrada: una vez montado y abierto, pasar a visible en el frame siguiente.
  useEffect(() => {
    if (isOpen && mounted) {
      const id = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(id);
    }
  }, [isOpen, mounted]);

  // Salida: al cerrar, ocultar (anima) y desmontar tras la transición.
  useEffect(() => {
    if (isOpen) return;
    const hideId = requestAnimationFrame(() => setVisible(false));
    const timeout = window.setTimeout(() => {
      setMounted(false);
      setDragY(0);
    }, ANIM_MS);
    return () => {
      cancelAnimationFrame(hideId);
      window.clearTimeout(timeout);
    };
  }, [isOpen]);

  // Cierre por Escape.
  useEffect(() => {
    if (!isOpen || disableEscapeClose) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, disableEscapeClose, onClose]);

  // Bloqueo de scroll del body mientras el modal está montado.
  useEffect(() => {
    if (!mounted) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mounted]);

  // Foco inicial al panel al abrir (accesibilidad).
  useEffect(() => {
    if (isOpen && visible) panelRef.current?.focus();
  }, [isOpen, visible]);

  // --- Swipe-down sobre el drag handle (solo mobile) ---
  const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    dragStartY.current = event.clientY;
    setDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (dragStartY.current === null) return;
    const delta = event.clientY - dragStartY.current;
    if (delta > 0) setDragY(delta); // solo hacia abajo
  }, []);

  const onPointerUp = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      setDragging(false);
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      const shouldClose = dragY > SWIPE_CLOSE_THRESHOLD;
      dragStartY.current = null;
      if (shouldClose) onClose();
      else setDragY(0);
    },
    [dragY, onClose]
  );

  if (!mounted) return null;

  const handleBackdropClick = () => {
    if (!disableBackdropClose) onClose();
  };

  // Estilo del panel según viewport: mobile = slide-up + drag; desktop = fade + scale.
  const panelStyle: CSSProperties = isMobile
    ? {
        transform: visible ? `translateY(${dragY}px)` : 'translateY(100%)',
        transition: dragging ? 'none' : `transform ${ANIM_MS}ms ${IOS_EASE}`,
      }
    : {
        transform: visible ? 'scale(1)' : 'scale(0.96)',
        opacity: visible ? 1 : 0,
        transition: `transform 180ms ease-out, opacity 180ms ease-out`,
      };

  // El bottom-sheet mobile NO muestra X (el drag handle + swipe + backdrop cierran);
  // en desktop o fullScreen sí, como única affordance clara de cierre.
  const showHandle = !fullScreen;

  const modalContent = (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? 'modal-title' : undefined}
    >
      {/* Backdrop (fade) */}
      <div
        aria-hidden="true"
        onClick={handleBackdropClick}
        className={cn(
          'absolute inset-0 bg-black/50 backdrop-blur-sm transition-opacity',
          visible ? 'opacity-100' : 'opacity-0'
        )}
        style={{ transitionDuration: `${ANIM_MS}ms`, transitionTimingFunction: IOS_EASE }}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        tabIndex={-1}
        className={cn(
          'relative w-full bg-card text-card-foreground shadow-lg border border-border',
          'flex flex-col overflow-hidden focus:outline-none',
          'rounded-t-2xl sm:rounded-lg',
          fullScreen
            ? 'h-[100dvh] sm:h-auto rounded-none sm:rounded-lg sm:max-h-[90vh]'
            : 'max-h-[100dvh] sm:max-h-[90vh]',
          sizeClasses[size],
          className
        )}
        style={panelStyle}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag handle (mobile): zona de swipe-down para cerrar. */}
        {showHandle && (
          <div
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            className="flex shrink-0 cursor-grab touch-none justify-center pt-3 pb-1 active:cursor-grabbing sm:hidden"
            aria-hidden="true"
          >
            <span className="h-1.5 w-12 rounded-full bg-border" />
          </div>
        )}

        {/* Header */}
        <div className="flex shrink-0 items-center justify-between gap-2 border-b border-border p-4 sm:p-6">
          {title && (
            <h2 id="modal-title" className="text-lg font-semibold text-foreground sm:text-xl">
              {title}
            </h2>
          )}
          <button
            onClick={onClose}
            className={cn(
              'ml-auto inline-flex min-h-11 min-w-11 items-center justify-center rounded-md p-2',
              'text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
              'touch-manipulation sm:min-h-0 sm:min-w-0 sm:p-1',
              // En el bottom-sheet (mobile, no fullScreen) se oculta: el handle/swipe cierran.
              showHandle && 'hidden sm:inline-flex'
            )}
            aria-label="Cerrar modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Content: scroll interno */}
        <div className="flex-1 overflow-y-auto overscroll-contain p-4 sm:p-6">{children}</div>

        {/* Footer: safe-area en mobile para que el teclado / home indicator no tapen */}
        {footer && (
          <div className="flex shrink-0 items-center justify-end gap-2 border-t border-border p-4 pb-[max(1rem,env(safe-area-inset-bottom))] sm:p-6 sm:pb-6">
            {footer}
          </div>
        )}
      </div>
    </div>
  );

  return createPortal(modalContent, document.body);
}
