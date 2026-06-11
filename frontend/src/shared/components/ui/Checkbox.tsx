import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

export interface CheckboxProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

/**
 * Checkbox con area de toque amplia (>=44px) sin cambiar el tamanio visual.
 *
 * Toda la fila (input + label) es un <label> clickeable: tocar cualquier parte
 * alterna el checkbox. El cuadrado visual se mantiene chico (h-4 w-4 en desktop,
 * h-5 w-5 en mobile) pero la fila garantiza el hit-area tactil.
 */
export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="flex flex-col">
        <label
          htmlFor={props.id}
          className={cn(
            'flex items-start gap-2 min-h-[44px] py-2 touch-manipulation',
            props.disabled ? 'cursor-not-allowed' : 'cursor-pointer'
          )}
        >
          <span className="flex items-center h-5 shrink-0">
            <input
              type="checkbox"
              ref={ref}
              className={cn(
                'h-5 w-5 sm:h-4 sm:w-4 rounded border-input text-accent focus:ring-ring',
                'transition duration-150 ease-in-out',
                'disabled:opacity-50 disabled:cursor-not-allowed',
                error && 'border-destructive focus:ring-destructive',
                className
              )}
              {...props}
            />
          </span>
          {label && (
            <span
              className={cn(
                'text-sm font-medium text-foreground self-center',
                props.disabled && 'opacity-50'
              )}
            >
              {label}
            </span>
          )}
        </label>
        {error && <p className="text-sm text-destructive ml-7 -mt-1">{error}</p>}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';
