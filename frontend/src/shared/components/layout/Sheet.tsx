import { useCallback, useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/shared/utils';

interface SheetProps {
  /** Controla la visibilidad del sheet. */
  open: boolean;
  /** Se invoca al pedir cierre (backdrop, Escape, swipe-down, botón). */
  onClose: () => void;
  /** Contenido del panel. */
  children: ReactNode;
  /** Título accesible del diálogo (para `aria-label`). */
  title?: string;
  /** Clases extra para el panel. */
  className?: string;
}

// Easing iOS para el deslizamiento del panel.
const IOS_EASE = 'cubic-bezier(0.32,0.72,0,1)';
// Umbral en px de arrastre vertical a partir del cual el swipe-down cierra el sheet.
const SWIPE_CLOSE_THRESHOLD = 80;

/**
 * Bottom-sheet reusable y accesible.
 *
 * - Se monta en un portal sobre `document.body`.
 * - `role="dialog" aria-modal="true"` + focus-trap básico (Tab cicla dentro).
 * - Bloquea el scroll del body mientras está abierto.
 * - Cierra por: tap en backdrop, tecla Escape y swipe-down sobre el drag handle.
 * - Respeta safe-area inferior (home indicator) con `env(safe-area-inset-bottom)`.
 * - Animación translate-y (slide-up) + fade del backdrop con easing iOS, sin
 *   depender de utilidades CSS externas (compila aunque F0 no esté aplicado).
 */
export const Sheet = ({ open, onClose, children, title, className }: SheetProps) => {
  // `mounted` mantiene el nodo en el DOM durante la animación de salida.
  const [mounted, setMounted] = useState(open);
  // `visible` dispara la transición de entrada (translate de 100% → 0) en el frame siguiente.
  const [visible, setVisible] = useState(false);
  // Offset vertical durante el arrastre (swipe-down).
  const [dragY, setDragY] = useState(0);
  const [dragging, setDragging] = useState(false);

  const panelRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef<number | null>(null);
  // Elemento enfocado antes de abrir, para restaurar el foco al cerrar.
  const lastFocused = useRef<HTMLElement | null>(null);

  // Montaje inmediato al abrir: ajuste de estado durante el render (patrón válido de
  // React) para que el portal exista en el mismo frame y la animación de entrada
  // pueda dispararse, sin llamar a setState sincrónicamente dentro de un efecto.
  if (open && !mounted) {
    setMounted(true);
  }

  // Animación de entrada: una vez montado y abierto, guardar el foco previo y pasar
  // a visible en el frame siguiente (callback async → permitido dentro del efecto).
  useEffect(() => {
    if (open && mounted) {
      lastFocused.current = document.activeElement as HTMLElement | null;
      const id = requestAnimationFrame(() => setVisible(true));
      return () => cancelAnimationFrame(id);
    }
  }, [open, mounted]);

  // Animación de salida: al cerrar, ocultar y desmontar tras la transición.
  useEffect(() => {
    if (open) return;
    const hideId = requestAnimationFrame(() => setVisible(false));
    const timeout = window.setTimeout(() => {
      setMounted(false);
      setDragY(0);
      // Restaurar foco al disparador original.
      lastFocused.current?.focus?.();
    }, 300);
    return () => {
      cancelAnimationFrame(hideId);
      window.clearTimeout(timeout);
    };
  }, [open]);

  // Bloqueo de scroll del body mientras el sheet está montado.
  useEffect(() => {
    if (!mounted) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [mounted]);

  // Cierre por Escape + focus-trap básico (Tab/Shift+Tab ciclan dentro del panel).
  useEffect(() => {
    if (!open) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;

      const panel = panelRef.current;
      if (!panel) return;
      const focusables = panel.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      );
      if (focusables.length === 0) {
        event.preventDefault();
        panel.focus();
        return;
      }
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && active === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && active === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  // Foco inicial al panel al abrir.
  useEffect(() => {
    if (open && visible) {
      panelRef.current?.focus();
    }
  }, [open, visible]);

  // --- Swipe-down sobre el drag handle ---
  const onPointerDown = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    dragStartY.current = event.clientY;
    setDragging(true);
    event.currentTarget.setPointerCapture(event.pointerId);
  }, []);

  const onPointerMove = useCallback((event: React.PointerEvent<HTMLDivElement>) => {
    if (dragStartY.current === null) return;
    const delta = event.clientY - dragStartY.current;
    // Solo permitir arrastrar hacia abajo.
    if (delta > 0) setDragY(delta);
  }, []);

  const onPointerUp = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      setDragging(false);
      event.currentTarget.releasePointerCapture?.(event.pointerId);
      const shouldClose = dragY > SWIPE_CLOSE_THRESHOLD;
      dragStartY.current = null;
      if (shouldClose) {
        onClose();
      } else {
        setDragY(0);
      }
    },
    [dragY, onClose]
  );

  if (!mounted) return null;

  // translateY combinado: 100% (oculto) → 0 (visible), más el offset de arrastre.
  const panelTransform = visible
    ? `translateY(${dragY}px)`
    : 'translateY(100%)';

  return createPortal(
    <div className="lg:hidden">
      {/* Backdrop */}
      <div
        aria-hidden="true"
        onClick={onClose}
        className={cn(
          'fixed inset-0 z-40 bg-black/50 transition-opacity duration-300',
          visible ? 'opacity-100' : 'opacity-0'
        )}
        style={{ transitionTimingFunction: IOS_EASE }}
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        className={cn(
          'fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col overflow-hidden',
          'rounded-t-2xl border-t border-border bg-card text-card-foreground shadow-2xl',
          'pb-[env(safe-area-inset-bottom)] focus:outline-none',
          className
        )}
        style={{
          transform: panelTransform,
          transition: dragging ? 'none' : `transform 300ms ${IOS_EASE}`,
        }}
      >
        {/* Drag handle: zona de swipe-down para cerrar. */}
        <div
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          className="flex shrink-0 cursor-grab touch-none justify-center py-3 active:cursor-grabbing"
          aria-hidden="true"
        >
          <span className="h-1.5 w-12 rounded-full bg-border" />
        </div>

        {/* Contenido scrollable */}
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">{children}</div>
      </div>
    </div>,
    document.body
  );
};
