import { forwardRef, type SelectHTMLAttributes } from 'react';
import { ChevronDown, Info } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  /**
   * Label text displayed above the select
   */
  label?: string;

  /**
   * Error message to display below select
   * When provided, select gets error styling
   */
  error?: string;

  /**
   * Helper text displayed below select when no error
   */
  helperText?: string;

  /**
   * Tooltip content shown next to label
   */
  tooltip?: string;

  /**
   * Options for the select dropdown
   */
  options?: SelectOption[];

  /**
   * Placeholder option text
   */
  placeholder?: string;

  /**
   * Additional wrapper class name
   */
  wrapperClassName?: string;
}

/**
 * Select component with label, error handling, and optional tooltip.
 *
 * @example
 * ```tsx
 * <Select
 *   label="Materia"
 *   placeholder="Selecciona una materia"
 *   tooltip="La materia a la que pertenece la comisión"
 *   options={[
 *     { value: '1', label: 'Programación 1' },
 *     { value: '2', label: 'Programación 2' },
 *   ]}
 *   error={errors.materia?.message}
 * />
 * ```
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      className,
      wrapperClassName,
      label,
      error,
      helperText,
      tooltip,
      options,
      placeholder,
      id,
      children,
      ...props
    },
    ref
  ) => {
    const selectId = id || `select-${Math.random().toString(36).substr(2, 9)}`;
    const hasError = Boolean(error);

    return (
      <div className={cn('space-y-1.5', wrapperClassName)}>
        {/* Label with optional tooltip */}
        {label && (
          <div className="flex items-center gap-1.5">
            <label
              htmlFor={selectId}
              className="text-sm font-medium text-foreground"
            >
              {label}
            </label>
            {tooltip && (
              <div
                className="group relative"
                role="tooltip"
                aria-label={tooltip}
              >
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

        {/* Select field */}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              // Base styles
              // Altura táctil >=44px y text-base (16px) en mobile para evitar el
              // auto-zoom de iOS; en sm: vuelve al look desktop actual (h-10, text-sm).
              'flex w-full rounded-md border bg-background px-3 py-2 text-base sm:text-sm h-11 sm:h-10',
              // touch-manipulation: mata el delay de 300ms y el doble-tap-zoom en mobile
              'touch-manipulation',
              'transition-colors appearance-none cursor-pointer',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50',
              // Icon spacing
              'pr-10',
              // State styles
              hasError
                ? 'border-destructive focus-visible:ring-destructive'
                : 'border-input focus-visible:ring-ring',
              className
            )}
            aria-invalid={hasError}
            aria-describedby={
              error ? `${selectId}-error` : helperText ? `${selectId}-helper` : undefined
            }
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}

            {options?.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
              >
                {option.label}
              </option>
            ))}

            {children}
          </select>

          {/* Chevron icon */}
          <ChevronDown
            className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none"
            aria-hidden="true"
          />
        </div>

        {/* Error or helper text */}
        {error && (
          <p
            id={`${selectId}-error`}
            className="text-sm text-destructive"
            role="alert"
          >
            {error}
          </p>
        )}

        {!error && helperText && (
          <p
            id={`${selectId}-helper`}
            className="text-sm text-muted-foreground"
          >
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
