import type { HTMLAttributes } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

export interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  /**
   * Size of the spinner
   * - sm: 16px
   * - default: 20px
   * - lg: 24px
   * - xl: 32px
   */
  size?: 'sm' | 'default' | 'lg' | 'xl';

  /**
   * Optional label text displayed below spinner
   */
  label?: string;
}

const spinnerSizes = {
  sm: 'h-4 w-4',
  default: 'h-5 w-5',
  lg: 'h-6 w-6',
  xl: 'h-8 w-8',
};

/**
 * Spinner component for loading states.
 *
 * @example
 * ```tsx
 * <Spinner />
 * <Spinner size="lg" label="Cargando entregas..." />
 * <Spinner size="sm" />
 * ```
 */
export function Spinner({
  className,
  size = 'default',
  label,
  ...props
}: SpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label || 'Cargando'}
      className={cn('flex flex-col items-center justify-center gap-2', className)}
      {...props}
    >
      <Loader2
        className={cn('animate-spin text-muted-foreground', spinnerSizes[size])}
        aria-hidden="true"
      />
      {label && (
        <span className="text-sm text-muted-foreground">{label}</span>
      )}
    </div>
  );
}
