import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

export interface CheckboxProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ className, label, error, ...props }, ref) => {
    return (
      <div className="flex items-start">
        <div className="flex items-center h-5">
          <input
            type="checkbox"
            ref={ref}
            className={cn(
              'h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500',
              'transition duration-150 ease-in-out',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              error && 'border-red-300 focus:ring-red-500',
              className
            )}
            {...props}
          />
        </div>
        {(label || error) && (
          <div className="ml-2 text-sm">
            {label && (
              <label
                htmlFor={props.id}
                className={cn(
                  'font-medium text-gray-700',
                  props.disabled && 'opacity-50 cursor-not-allowed'
                )}
              >
                {label}
              </label>
            )}
            {error && <p className="text-red-600 mt-1">{error}</p>}
          </div>
        )}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';
