import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react';
import { Info } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /**
   * Label text displayed above the input
   */
  label?: string;

  /**
   * Error message to display below input
   * When provided, input gets error styling
   */
  error?: string;

  /**
   * Helper text displayed below input when no error
   */
  helperText?: string;

  /**
   * Tooltip content shown next to label
   */
  tooltip?: string;

  /**
   * Icon to display at the start of the input
   */
  startIcon?: ReactNode;

  /**
   * Icon to display at the end of the input
   */
  endIcon?: ReactNode;

  /**
   * Additional wrapper class name
   */
  wrapperClassName?: string;
}

/**
 * Input component with label, error handling, and optional tooltip.
 *
 * @example
 * ```tsx
 * <Input
 *   label="Nombre de usuario"
 *   placeholder="jperez"
 *   tooltip="Tu identificador único en el sistema"
 *   error={errors.username?.message}
 * />
 *
 * <Input
 *   label="Email"
 *   type="email"
 *   helperText="Usaremos este email para notificaciones"
 * />
 * ```
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      wrapperClassName,
      label,
      error,
      helperText,
      tooltip,
      startIcon,
      endIcon,
      id,
      ...props
    },
    ref
  ) => {
    // UI-010: useId() da un id estable entre renders (Math.random() lo regeneraba
    // en cada render, rompiendo password managers, autofill y selectores de test).
    const generatedId = useId();
    const inputId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className={cn('space-y-1.5', wrapperClassName)}>
        {/* Label with optional tooltip */}
        {label && (
          <div className="flex items-center gap-1.5">
            <label
              htmlFor={inputId}
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

        {/* Input field with optional icons */}
        <div className="relative">
          {startIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {startIcon}
            </div>
          )}

          <input
            ref={ref}
            id={inputId}
            className={cn(
              // Base styles
              // Altura táctil >=44px y text-base (16px) en mobile para evitar el
              // auto-zoom de iOS; en sm: vuelve al look desktop actual (h-10, text-sm).
              'flex w-full rounded-md border bg-background px-3 py-2 text-base sm:text-sm h-11 sm:h-10',
              // touch-manipulation: mata el delay de 300ms y el doble-tap-zoom en mobile
              'touch-manipulation',
              'transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium',
              'placeholder:text-muted-foreground',
              'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2',
              'disabled:cursor-not-allowed disabled:opacity-50',
              // Icon spacing
              startIcon && 'pl-10',
              endIcon && 'pr-10',
              // State styles
              hasError
                ? 'border-destructive focus-visible:ring-destructive'
                : 'border-input focus-visible:ring-ring',
              className
            )}
            aria-invalid={hasError}
            aria-describedby={
              error ? `${inputId}-error` : helperText ? `${inputId}-helper` : undefined
            }
            {...props}
          />

          {endIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground">
              {endIcon}
            </div>
          )}
        </div>

        {/* Error or helper text */}
        {error && (
          <p
            id={`${inputId}-error`}
            className="text-sm text-destructive"
            role="alert"
          >
            {error}
          </p>
        )}

        {!error && helperText && (
          <p
            id={`${inputId}-helper`}
            className="text-sm text-muted-foreground"
          >
            {helperText}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
