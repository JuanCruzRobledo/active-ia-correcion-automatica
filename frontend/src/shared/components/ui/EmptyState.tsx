// shared/components/ui/EmptyState.tsx
/**
 * EmptyState component for displaying empty states
 * Ref: docs/specs/07-DISENO-UI-UX.md section 8.1
 */

import { type ReactNode } from 'react';
import { cn } from '@/shared/utils/cn';

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

export const EmptyState = ({
  icon = '📭',
  title,
  description,
  action,
  className,
}: EmptyStateProps) => {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center py-8 sm:py-12 px-4',
        className
      )}
    >
      <div className="text-5xl sm:text-6xl mb-4">{icon}</div>
      <h3 className="text-lg font-medium text-foreground mb-2 text-center">{title}</h3>
      {description && (
        <p className="text-sm text-muted-foreground text-center max-w-md mb-6">
          {description}
        </p>
      )}
      {/* Accion full-width en mobile (boton ocupa el ancho), auto en desktop. */}
      {action && (
        <div className="w-full sm:w-auto [&>*]:w-full sm:[&>*]:w-auto">{action}</div>
      )}
    </div>
  );
};
