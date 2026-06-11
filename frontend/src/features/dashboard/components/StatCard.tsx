/**
 * StatCard - Reusable statistic card component.
 *
 * Displays a numeric stat with icon, title, and subtitle.
 * Supports different variants for visual feedback.
 *
 * Ref: docs/specs/08-SISTEMA-DISENO-ESTILOS.md Section 7.2
 */

import type { LucideIcon } from 'lucide-react';
import { cn } from '@/shared/utils/cn';

interface StatCardProps {
  /**
   * Card title
   */
  title: string;

  /**
   * Main numeric value
   */
  value: number;

  /**
   * Subtitle text (e.g., "activas", "pendientes")
   */
  subtitle: string;

  /**
   * Lucide icon component
   */
  icon: LucideIcon;

  /**
   * Visual variant
   */
  variant?: 'default' | 'success' | 'warning' | 'destructive';
}

const variantStyles = {
  default: 'bg-card border-border',
  success: 'bg-success/10 border-success/20',
  warning: 'bg-warning/10 border-warning/20',
  destructive: 'bg-destructive/10 border-destructive/20',
};

const iconVariantStyles = {
  default: 'text-muted-foreground',
  success: 'text-success',
  warning: 'text-warning',
  destructive: 'text-destructive',
};

export function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
  variant = 'default',
}: StatCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border p-4 transition-colors sm:p-6',
        variantStyles[variant]
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-sm font-medium text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold text-foreground sm:text-3xl">{value}</p>
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        </div>
        <div
          className={cn(
            'shrink-0 rounded-full bg-muted/50 p-3',
            iconVariantStyles[variant]
          )}
        >
          <Icon className="h-6 w-6" />
        </div>
      </div>
    </div>
  );
}
