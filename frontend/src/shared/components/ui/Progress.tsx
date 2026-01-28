/**
 * Progress - Progress bar component.
 *
 * Displays a horizontal progress bar with customizable value and appearance.
 *
 * Ref: docs/specs/08-SISTEMA-DISENO-ESTILOS.md Section 7.1
 * Ref: skills/react-typescript/SKILL.md
 */

import { cn } from '@/shared/utils/cn';

export interface ProgressProps {
  /**
   * Progress value (0-100)
   */
  value: number;

  /**
   * Additional CSS classes
   */
  className?: string;

  /**
   * Visual variant
   */
  variant?: 'default' | 'success' | 'warning' | 'destructive';
}

const variantStyles = {
  default: 'bg-accent',
  success: 'bg-success',
  warning: 'bg-warning',
  destructive: 'bg-destructive',
};

export function Progress({
  value,
  className,
  variant = 'default',
}: ProgressProps) {
  // Clamp value between 0 and 100
  const clampedValue = Math.min(100, Math.max(0, value));

  // Determine variant based on value if not explicitly set
  let effectiveVariant = variant;
  if (variant === 'default') {
    if (clampedValue === 100) {
      effectiveVariant = 'success';
    } else if (clampedValue < 50) {
      effectiveVariant = 'warning';
    }
  }

  return (
    <div
      className={cn(
        'relative h-2 w-full overflow-hidden rounded-full bg-secondary',
        className
      )}
    >
      <div
        className={cn(
          'h-full rounded-full transition-all duration-300',
          variantStyles[effectiveVariant]
        )}
        style={{ width: `${clampedValue}%` }}
      />
    </div>
  );
}
