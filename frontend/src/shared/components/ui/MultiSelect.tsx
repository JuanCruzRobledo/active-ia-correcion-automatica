import { useState, useRef, useEffect } from 'react';
import { Check, ChevronDown, Info, X } from 'lucide-react';
import { createPortal } from 'react-dom';
import { cn } from '../../utils/cn';

export interface MultiSelectOption {
  value: number;
  label: string;
  disabled?: boolean;
}

export interface MultiSelectProps {
  /** Label text displayed above the select */
  label?: string;
  /** Error message to display below select */
  error?: string;
  /** Helper text displayed below select when no error */
  helperText?: string;
  /** Tooltip content shown next to label */
  tooltip?: string;
  /** Options for the multi-select */
  options: MultiSelectOption[];
  /** Currently selected values (array of option values) */
  value: number[];
  /** Callback when selection changes */
  onChange: (value: number[]) => void;
  /** Placeholder text when no selection */
  placeholder?: string;
  /** Additional wrapper class name */
  wrapperClassName?: string;
  /** Disable the select */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
}

/** Media query para detectar mobile (Tailwind: base = mobile, sm: = >=640px). */
const MOBILE_QUERY = '(max-width: 639px)';

/**
 * MultiSelect component with checkboxes for multiple selection.
 *
 * Mobile (< 640px): el listado abre como bottom-sheet full-width anclado abajo,
 * con backdrop e items grandes (>=44px). Desktop (>= 640px): dropdown flotante
 * posicionado por coordenadas (look intacto), reposicionado con visualViewport
 * para que el teclado virtual no lo tape.
 *
 * El dropdown se renderiza via React Portal para aparecer siempre por encima de
 * los overlays de los modales, sin importar overflow/stacking context del padre.
 */
export const MultiSelect = ({
  label,
  error,
  helperText,
  tooltip,
  options,
  value,
  onChange,
  placeholder = 'Seleccionar...',
  wrapperClassName,
  disabled = false,
  loading = false,
}: MultiSelectProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [dropdownStyle, setDropdownStyle] = useState<React.CSSProperties>({});
  const [isMobile, setIsMobile] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Ref to the portal dropdown so clicks inside it don't trigger "click outside"
  const dropdownRef = useRef<HTMLDivElement>(null);
  const hasError = Boolean(error);

  // Detecta mobile de forma reactiva.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mql = window.matchMedia(MOBILE_QUERY);
    const update = () => setIsMobile(mql.matches);
    update();
    mql.addEventListener('change', update);
    return () => mql.removeEventListener('change', update);
  }, []);

  // Close dropdown only when clicking outside BOTH the trigger container AND the portal dropdown
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      const insideTrigger = containerRef.current?.contains(target) ?? false;
      const insideDropdown = dropdownRef.current?.contains(target) ?? false;
      if (!insideTrigger && !insideDropdown) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }
  }, [isOpen]);

  // Cierre por Escape (accesibilidad).
  useEffect(() => {
    if (!isOpen) return;
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setIsOpen(false);
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen]);

  // Bloquea el scroll del body mientras el bottom-sheet mobile esta abierto.
  useEffect(() => {
    if (!isOpen || !isMobile) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previous;
    };
  }, [isOpen, isMobile]);

  // Desktop: computa posicion fija desde el bounding rect del trigger.
  // Abre hacia abajo por defecto; se voltea hacia arriba si no hay espacio.
  // Se reposiciona con visualViewport (resize/scroll) para que el teclado
  // virtual no tape el listado.
  useEffect(() => {
    if (!isOpen || isMobile || !triggerRef.current) return;

    const updatePosition = () => {
      const rect = triggerRef.current!.getBoundingClientRect();
      const DROPDOWN_MAX_HEIGHT = 240; // matches max-h-60 = 15rem ≈ 240px
      const MARGIN = 4;
      const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
      const spaceBelow = viewportHeight - rect.bottom - MARGIN;
      const spaceAbove = rect.top - MARGIN;
      const openUpward = spaceBelow < DROPDOWN_MAX_HEIGHT && spaceAbove > spaceBelow;
      const availableHeight = openUpward
        ? Math.min(DROPDOWN_MAX_HEIGHT, spaceAbove)
        : Math.min(DROPDOWN_MAX_HEIGHT, spaceBelow);

      setDropdownStyle({
        position: 'fixed',
        ...(openUpward
          ? { bottom: viewportHeight - rect.top + MARGIN }
          : { top: rect.bottom + MARGIN }),
        left: rect.left,
        width: rect.width,
        maxHeight: availableHeight,
        zIndex: 9999,
      });
    };

    updatePosition();
    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);
    window.visualViewport?.addEventListener('resize', updatePosition);
    window.visualViewport?.addEventListener('scroll', updatePosition);
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
      window.visualViewport?.removeEventListener('resize', updatePosition);
      window.visualViewport?.removeEventListener('scroll', updatePosition);
    };
  }, [isOpen, isMobile]);

  const toggleOption = (optionValue: number) => {
    if (disabled) return;
    if (value.includes(optionValue)) {
      onChange(value.filter((v) => v !== optionValue));
    } else {
      onChange([...value, optionValue]);
    }
  };

  const removeOption = (optionValue: number) => {
    onChange(value.filter((v) => v !== optionValue));
  };

  const selectedOptions = options.filter((opt) => value.includes(opt.value));
  const displayText =
    selectedOptions.length > 0
      ? `${selectedOptions.length} seleccionado${selectedOptions.length > 1 ? 's' : ''}`
      : placeholder;

  // Lista de opciones (compartida entre desktop y mobile).
  const optionsList =
    options.length === 0 ? (
      <div className="px-2 py-6 text-center text-sm text-muted-foreground">
        No hay opciones disponibles
      </div>
    ) : (
      options.map((option) => (
        <button
          key={option.value}
          type="button"
          onClick={() => {
            toggleOption(option.value);
          }}
          disabled={option.disabled}
          className={cn(
            'flex w-full items-center gap-2 rounded-sm text-left touch-manipulation',
            // Mobile: items grandes y tocables (>=44px). Desktop: look original.
            'min-h-[44px] px-3 py-3 text-base sm:min-h-0 sm:px-2 sm:py-1.5 sm:text-sm',
            'hover:bg-accent hover:text-accent-foreground transition-colors',
            'disabled:opacity-50 disabled:cursor-not-allowed'
          )}
        >
          <div
            className={cn(
              'h-5 w-5 sm:h-4 sm:w-4 rounded border flex items-center justify-center shrink-0',
              value.includes(option.value)
                ? 'bg-primary border-primary'
                : 'border-input'
            )}
          >
            {value.includes(option.value) && (
              <Check className="h-3.5 w-3.5 sm:h-3 sm:w-3 text-primary-foreground" />
            )}
          </div>
          <span>{option.label}</span>
        </button>
      ))
    );

  // Dropdown rendered into document.body via Portal to escape modal stacking context.
  // dropdownRef is used so the click-outside handler won't close the menu when
  // the user clicks an option inside the portal.
  let dropdown: React.ReactNode = null;

  if (isOpen && !loading && isMobile) {
    // Bottom-sheet full-width anclado abajo, con backdrop tocable para cerrar.
    dropdown = (
      <div className="fixed inset-0 z-[9999] flex flex-col justify-end">
        <div
          className="absolute inset-0 bg-black/50"
          onClick={() => setIsOpen(false)}
          aria-hidden="true"
        />
        <div
          ref={dropdownRef}
          className={cn(
            'relative w-full bg-popover border-t border-border shadow-md',
            'rounded-t-2xl max-h-[85dvh] overflow-y-auto overscroll-contain',
            'pb-[max(0.5rem,env(safe-area-inset-bottom))]',
            'animate-in fade-in-0 slide-in-from-bottom-4 duration-200'
          )}
        >
          {/* Drag handle visual */}
          <div className="mx-auto mt-2 mb-1 h-1.5 w-12 rounded-full bg-border" />
          {label && (
            <div className="px-3 pt-1 pb-2 text-sm font-medium text-foreground">
              {label}
            </div>
          )}
          <div className="p-1">{optionsList}</div>
        </div>
      </div>
    );
  } else if (isOpen && !loading) {
    // Desktop: dropdown flotante posicionado por coordenadas (look intacto).
    dropdown = (
      <div
        ref={dropdownRef}
        style={dropdownStyle}
        className="rounded-md border border-border bg-popover shadow-md overflow-y-auto"
      >
        <div className="p-1">{optionsList}</div>
      </div>
    );
  }

  return (
    <div className={cn('space-y-1.5', wrapperClassName)} ref={containerRef}>
      {/* Label with optional tooltip */}
      {label && (
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-foreground">{label}</label>
          {tooltip && (
            <div className="group relative" role="tooltip" aria-label={tooltip} tabIndex={0}>
              <Info className="h-4 w-4 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
              {/* focus-within:block ademas de group-hover:block para que sea accesible en touch (no hay hover) */}
              <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block group-focus-within:block z-50">
                <div className="bg-popover text-popover-foreground text-xs rounded-md px-3 py-1.5 shadow-md border border-border max-w-xs whitespace-normal">
                  {tooltip}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Selected items badges */}
      {selectedOptions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedOptions.map((option) => (
            <div
              key={option.value}
              className="inline-flex items-center gap-1 pl-2 pr-1 py-0.5 rounded-md bg-secondary text-secondary-foreground text-sm"
            >
              <span>{option.label}</span>
              <button
                type="button"
                onClick={() => removeOption(option.value)}
                disabled={disabled}
                aria-label={`Quitar ${option.label}`}
                className={cn(
                  'flex items-center justify-center rounded-sm touch-manipulation',
                  // Hit-area grande en mobile sin agrandar el badge en desktop.
                  'min-h-9 min-w-9 p-1.5 sm:min-h-0 sm:min-w-0 sm:p-0.5',
                  'hover:bg-secondary-foreground/10 transition-colors disabled:opacity-50'
                )}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Dropdown trigger */}
      <div className="relative">
        <button
          type="button"
          ref={triggerRef}
          onClick={() => !disabled && !loading && setIsOpen(!isOpen)}
          disabled={disabled || loading}
          className={cn(
            'flex w-full items-center justify-between rounded-md border bg-background touch-manipulation',
            // 16px en mobile evita auto-zoom iOS; altura >=44px tocable.
            'min-h-[44px] px-3 py-2.5 text-base sm:min-h-0 sm:py-2 sm:text-sm',
            'transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
            'disabled:cursor-not-allowed disabled:opacity-50',
            hasError
              ? 'border-destructive focus-visible:ring-destructive'
              : 'border-input focus-visible:ring-ring',
            isOpen && 'ring-2 ring-offset-2 ring-ring'
          )}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
        >
          <span className={cn(selectedOptions.length === 0 && 'text-muted-foreground')}>
            {loading ? 'Cargando...' : displayText}
          </span>
          <ChevronDown
            className={cn(
              'h-4 w-4 text-muted-foreground transition-transform',
              isOpen && 'rotate-180'
            )}
          />
        </button>

        {/* Portal: renders dropdown outside any overflow/stacking context */}
        {typeof document !== 'undefined' && createPortal(dropdown, document.body)}
      </div>

      {/* Error or helper text */}
      {error && (
        <p className="text-sm text-destructive" role="alert">
          {error}
        </p>
      )}
      {!error && helperText && (
        <p className="text-sm text-muted-foreground">{helperText}</p>
      )}
    </div>
  );
};
