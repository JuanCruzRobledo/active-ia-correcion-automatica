import { forwardRef } from 'react';
import { cn } from '@/shared/utils/cn';

export interface RadioProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label: string;
  description?: string;
  error?: string;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
  ({ className, label, description, error, ...props }, ref) => {
    return (
      <div className="flex items-start">
        <div className="flex items-center h-5">
          <input
            type="radio"
            ref={ref}
            className={cn(
              'h-4 w-4 border-gray-300 text-blue-600 focus:ring-blue-500',
              'transition duration-150 ease-in-out',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              error && 'border-red-300 focus:ring-red-500',
              className
            )}
            {...props}
          />
        </div>
        <div className="ml-3 text-sm">
          <label
            htmlFor={props.id}
            className={cn(
              'font-medium text-gray-700',
              props.disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {label}
          </label>
          {description && (
            <p className="text-gray-500">{description}</p>
          )}
          {error && <p className="text-red-600 mt-1">{error}</p>}
        </div>
      </div>
    );
  }
);

Radio.displayName = 'Radio';
