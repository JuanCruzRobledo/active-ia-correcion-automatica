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

/**
 * MultiSelect component with checkboxes for multiple selection.
 *
 * The dropdown is rendered via a React Portal so it always appears above
 * modal overlays regardless of parent overflow or stacking context.
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
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Ref to the portal dropdown so clicks inside it don't trigger "click outside"
  const dropdownRef = useRef<HTMLDivElement>(null);
  const hasError = Boolean(error);

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

  // Compute fixed position from trigger's bounding rect.
  // Opens downward by default; flips upward if there isn't enough space below.
  useEffect(() => {
    if (!isOpen || !triggerRef.current) return;

    const updatePosition = () => {
      const rect = triggerRef.current!.getBoundingClientRect();
      const DROPDOWN_MAX_HEIGHT = 240; // matches max-h-60 = 15rem ≈ 240px
      const MARGIN = 4;
      const spaceBelow = window.innerHeight - rect.bottom - MARGIN;
      const spaceAbove = rect.top - MARGIN;
      const openUpward = spaceBelow < DROPDOWN_MAX_HEIGHT && spaceAbove > spaceBelow;
      const availableHeight = openUpward
        ? Math.min(DROPDOWN_MAX_HEIGHT, spaceAbove)
        : Math.min(DROPDOWN_MAX_HEIGHT, spaceBelow);

      setDropdownStyle({
        position: 'fixed',
        ...(openUpward
          ? { bottom: window.innerHeight - rect.top + MARGIN }
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
    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen]);

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

  // Dropdown rendered into document.body via Portal to escape modal stacking context.
  // dropdownRef is used so the click-outside handler won't close the menu when
  // the user clicks an option inside the portal.
  const dropdown = isOpen && !loading && (
    <div
      ref={dropdownRef}
      style={dropdownStyle}
      className="rounded-md border border-border bg-popover shadow-md overflow-y-auto"
    >
      <div className="p-1">
        {options.length === 0 ? (
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
                'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm text-left',
                'hover:bg-accent hover:text-accent-foreground transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              <div
                className={cn(
                  'h-4 w-4 rounded border flex items-center justify-center shrink-0',
                  value.includes(option.value)
                    ? 'bg-primary border-primary'
                    : 'border-input'
                )}
              >
                {value.includes(option.value) && (
                  <Check className="h-3 w-3 text-primary-foreground" />
                )}
              </div>
              <span>{option.label}</span>
            </button>
          ))
        )}
      </div>
    </div>
  );

  return (
    <div className={cn('space-y-1.5', wrapperClassName)} ref={containerRef}>
      {/* Label with optional tooltip */}
      {label && (
        <div className="flex items-center gap-1.5">
          <label className="text-sm font-medium text-foreground">{label}</label>
          {tooltip && (
            <div className="group relative" role="tooltip" aria-label={tooltip}>
              <Info className="h-4 w-4 text-muted-foreground hover:text-foreground transition-colors cursor-help" />
              <div className="absolute left-0 bottom-full mb-2 hidden group-hover:block z-50">
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
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground text-sm"
            >
              <span>{option.label}</span>
              <button
                type="button"
                onClick={() => removeOption(option.value)}
                disabled={disabled}
                className="hover:bg-secondary-foreground/10 rounded-sm transition-colors disabled:opacity-50"
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
            'flex w-full items-center justify-between rounded-md border bg-background px-3 py-2 text-sm',
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
