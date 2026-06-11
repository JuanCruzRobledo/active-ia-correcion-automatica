// shared/components/ui/Dropdown.tsx
/**
 * Dropdown menu component for actions with portal support
 * Uses React Portal to render menu outside of overflow containers
 *
 * Mobile (< 640px): el menu se comporta como un action-sheet anclado abajo,
 * full-width, con backdrop e items grandes y tocables (>=44px).
 * Desktop (>= 640px): menu flotante posicionado por coordenadas (look intacto).
 *
 * Ref: docs/specs/07-DISENO-UI-UX.md
 */

import { type ReactNode, useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/shared/utils/cn';

export interface DropdownItem {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  variant?: 'default' | 'danger';
  disabled?: boolean;
}

export interface DropdownProps {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: 'left' | 'right';
  className?: string;
}

/** Media query para detectar mobile (Tailwind: base = mobile, sm: = >=640px). */
const MOBILE_QUERY = '(max-width: 639px)';

export const Dropdown = ({
  trigger,
  items,
  align = 'right',
  className,
}: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, bottom: 0, left: 0, right: 0 });
  const [openUpward, setOpenUpward] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Detecta mobile de forma reactiva (sin romper SSR/desktop).
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia(MOBILE_QUERY);
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, []);

  // Calculate position when opening (solo desktop: en mobile es action-sheet fijo abajo)
  useEffect(() => {
    if (isMobile) return;
    if (isOpen && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();

      // Estimate menu height (approximate: 40px per item + padding)
      const estimatedMenuHeight = items.length * 40 + 16;
      const spaceBelow = window.innerHeight - rect.bottom;
      const spaceAbove = rect.top;

      // Decide whether to open upward or downward
      const shouldOpenUpward = spaceBelow < estimatedMenuHeight && spaceAbove > spaceBelow;
      setOpenUpward(shouldOpenUpward);

      setPosition({
        top: rect.bottom + window.scrollY + 8,
        bottom: window.innerHeight - rect.top - window.scrollY + 8,
        left: rect.left + window.scrollX,
        right: window.innerWidth - rect.right - window.scrollX,
      });
    }
  }, [isOpen, items.length, isMobile]);

  // Handle click outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        triggerRef.current &&
        !triggerRef.current.contains(event.target as Node) &&
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Handle scroll/resize - close menu.
  // En mobile el menu es un action-sheet fijo: los gestos tactiles scrollean y lo
  // cerrarian por accidente, asi que NO cerramos por scroll (solo desktop reposiciona/cierra).
  useEffect(() => {
    if (isMobile) return;

    const handleScrollOrResize = () => {
      setIsOpen(false);
    };

    if (isOpen) {
      window.addEventListener('scroll', handleScrollOrResize, true);
      window.addEventListener('resize', handleScrollOrResize);
    }

    return () => {
      window.removeEventListener('scroll', handleScrollOrResize, true);
      window.removeEventListener('resize', handleScrollOrResize);
    };
  }, [isOpen, isMobile]);

  // Cierre por Escape (accesibilidad, util tambien con teclado externo en tablet)
  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  const itemButtons = items.map((item, index) => (
    <button
      key={index}
      type="button"
      onClick={() => {
        if (!item.disabled) {
          item.onClick();
          setIsOpen(false);
        }
      }}
      disabled={item.disabled}
      className={cn(
        // Mobile: items grandes y tocables (>=44px). Desktop: look original.
        'w-full text-left flex items-center gap-2 touch-manipulation',
        'min-h-[44px] px-4 py-3 text-base sm:min-h-0 sm:py-2 sm:text-sm',
        'transition-colors',
        item.disabled
          ? 'text-muted-foreground cursor-not-allowed opacity-50'
          : item.variant === 'danger'
            ? 'text-destructive hover:bg-destructive/10'
            : 'text-foreground hover:bg-muted'
      )}
    >
      {item.icon && <span className="text-base">{item.icon}</span>}
      <span>{item.label}</span>
    </button>
  ));

  let menu: ReactNode = null;

  if (isOpen && isMobile) {
    // Action-sheet anclado abajo, full-width, con backdrop tocable para cerrar.
    menu = (
      <div className="fixed inset-0 z-50 flex flex-col justify-end">
        <div
          className="absolute inset-0 bg-black/50"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
        <div
          ref={menuRef}
          role="menu"
          className={cn(
            'relative w-full bg-card border-t border-border shadow-lg',
            'rounded-t-2xl max-h-[85dvh] overflow-y-auto overscroll-contain',
            'pb-[max(0.5rem,env(safe-area-inset-bottom))]',
            'animate-in fade-in-0 slide-in-from-bottom-4 duration-200'
          )}
        >
          {/* Drag handle visual */}
          <div className="mx-auto mt-2 mb-1 h-1.5 w-12 rounded-full bg-border" />
          <div className="py-1">{itemButtons}</div>
        </div>
      </div>
    );
  } else if (isOpen) {
    // Desktop: menu flotante posicionado por coordenadas (comportamiento original).
    menu = (
      <div
        ref={menuRef}
        role="menu"
        className={cn(
          'fixed z-50 w-56 rounded-md shadow-lg bg-card ring-1 ring-border',
          'animate-in fade-in-0 zoom-in-95 duration-100'
        )}
        style={{
          ...(openUpward
            ? { bottom: `${position.bottom}px` }
            : { top: `${position.top}px` }),
          [align === 'right' ? 'right' : 'left']:
            align === 'right' ? `${position.right}px` : `${position.left}px`,
        }}
      >
        <div className="py-1">{itemButtons}</div>
      </div>
    );
  }

  return (
    <>
      <div
        ref={triggerRef}
        className={cn('inline-block touch-manipulation', className)}
        onClick={() => setIsOpen(!isOpen)}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        {trigger}
      </div>
      {menu && createPortal(menu, document.body)}
    </>
  );
};
