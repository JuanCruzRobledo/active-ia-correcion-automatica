// shared/components/ui/Dropdown.tsx
/**
 * Dropdown menu component for actions with portal support
 * Uses React Portal to render menu outside of overflow containers
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

export const Dropdown = ({
  trigger,
  items,
  align = 'right',
  className,
}: DropdownProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, bottom: 0, left: 0, right: 0 });
  const [openUpward, setOpenUpward] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  // Calculate position when opening
  useEffect(() => {
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
  }, [isOpen, items.length]);

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

  // Handle scroll/resize - close menu
  useEffect(() => {
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
  }, [isOpen]);

  const menu = isOpen ? (
    <div
      ref={menuRef}
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
      <div className="py-1">
        {items.map((item, index) => (
          <button
            key={index}
            onClick={() => {
              if (!item.disabled) {
                item.onClick();
                setIsOpen(false);
              }
            }}
            disabled={item.disabled}
            className={cn(
              'w-full text-left px-4 py-2 text-sm flex items-center gap-2',
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
        ))}
      </div>
    </div>
  ) : null;

  return (
    <>
      <div
        ref={triggerRef}
        className={cn('inline-block', className)}
        onClick={() => setIsOpen(!isOpen)}
      >
        {trigger}
      </div>
      {menu && createPortal(menu, document.body)}
    </>
  );
};
