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
              'h-4 w-4 border-input text-accent focus:ring-ring',
              'transition duration-150 ease-in-out',
              'disabled:opacity-50 disabled:cursor-not-allowed',
              error && 'border-destructive focus:ring-destructive',
              className
            )}
            {...props}
          />
        </div>
        <div className="ml-3 text-sm">
          <label
            htmlFor={props.id}
            className={cn(
              'font-medium text-foreground',
              props.disabled && 'opacity-50 cursor-not-allowed'
            )}
          >
            {label}
          </label>
          {description && (
            <p className="text-muted-foreground">{description}</p>
          )}
          {error && <p className="text-destructive mt-1">{error}</p>}
        </div>
      </div>
    );
  }
);

Radio.displayName = 'Radio';
