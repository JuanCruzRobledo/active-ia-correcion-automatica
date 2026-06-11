import type { HTMLAttributes } from 'react';
import { cn } from '../../utils/cn';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  /**
   * Visual style variant of the badge
   * - default: General purpose (gray background)
   * - success: Completed/OK status (green)
   * - warning: Warning/pending status (yellow)
   * - destructive: Error/danger status (red)
   * - info: Informational status (blue)
   * - outline: Neutral with border (transparent bg)
   */
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'outline';
}

const badgeVariants = {
  default: 'bg-secondary text-secondary-foreground',
  success: 'bg-success/20 text-success border-success/30',
  warning: 'bg-warning/20 text-warning border-warning/30',
  destructive: 'bg-destructive/20 text-destructive border-destructive/30',
  info: 'bg-info/20 text-info border-info/30',
  outline: 'border border-border bg-background text-foreground',
};

/**
 * Badge component for displaying status, labels, or categories.
 *
 * NO interactivo: es un indicador de estado/etiqueta, no un control tactil.
 * Para chips tappables (filtros) usar una variante Chip dedicada con hit-area
 * >=44px; no agregar onClick a Badge.
 *
 * @example
 * ```tsx
 * <Badge variant="success">Corregido</Badge>
 * <Badge variant="warning">Pendiente</Badge>
 * <Badge variant="destructive">Error</Badge>
 * <Badge variant="info">Info</Badge>
 * <Badge variant="outline">Admin</Badge>
 * ```
 */
export function Badge({
  className,
  variant = 'default',
  ...props
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-2.5 py-0.5 text-xs font-medium',
        'transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        badgeVariants[variant],
        className
      )}
      {...props}
    />
  );
}
